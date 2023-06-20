import json
import re
from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.core import serializers
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
import random
import platform
import os
import pandas as pd
import time
import requests
import urllib.parse
import csv
from io import StringIO
import pickle
import traceback
from datetime import datetime

from .models import RawLevelData
from .serializers import RawLevelDataSerializer

def monitorIp(IP):

    allowed = True

    if platform.system() == "Windows":
        ipListPath = "C:/Users/Alex Grogan/Documents/code/tmp/"
    elif platform.system() == "Linux":
        ipListPath = "/home/alex/tmps/"
    elif platform.system() == "Darwin":
        ipListPath = "tmp/"

    # Check if file exists:
    if not os.path.exists(ipListPath + "ipList.txt"):
        with open(ipListPath + "ipList.txt", 'x') as f:
            f.write("timestamp ip\n")
            f.close()
    # Create blacklist
    if not os.path.exists(ipListPath + "ipBlacklist.txt"):
        with open(ipListPath + "ipBlacklist.txt", 'x') as f:
            f.write("ip\n")
            f.close()
    # Open file as pd dataframe
    # ---
    ipData = pd.read_csv(ipListPath + "ipList.txt", sep=" ", header=0)
    blacklist = pd.read_csv(ipListPath + "ipBlacklist.txt", sep=" ", header=0)
    if IP in str(ipData["ip"]):
        # Compute request rate
        # v = ipData.ip.value_counts() # <-- Counts occurences of all unique IPs
        inst = ipData[ipData.ip.isin([IP])]
        n = int(inst.shape[0]/10) + 1 # make n proportional to the number of occurences
        checks = random.sample(inst.index.values.tolist(), n)
        checks.append(-1)
        for check in checks:
            start = inst.iloc[[0]]
            end = inst.loc[[check]] if check != -1 else inst.iloc[[check]]
            if check / (end.iloc[0]["timestamp"] - start.iloc[0]["timestamp"]) > 10000: # i.e n attempts per d seconds
                # blacklist IP
                if IP not in str(blacklist["ip"]):
                    blacklist.loc[blacklist.shape[0]] = [IP]

    if IP in str(blacklist["ip"]):
        allowed = False

    ipData.loc[ipData.shape[0]] = [time.time(), IP]
    # ---
    # save
    ipData.to_csv(ipListPath + "ipList.txt", header=["timestamp", "ip"], sep=" ", index=None)
    blacklist.to_csv(ipListPath + "ipBlacklist.txt", header=["ip"], sep=" ", index=None)

    return allowed

def removeBlacklistedIp(request, IP):

    IP = IP.replace("%", '.')

    if not request.user.is_authenticated:
        return HttpResponse(status=403)

    if platform.system() == "Windows":
        ipListPath = "C:/Users/Alex Grogan/Documents/code/tmp/"
    elif platform.system() == "Linux":
        ipListPath = "tmp/"

    if os.path.exists(ipListPath+"ipBlacklist.txt"):
        blacklist = pd.read_csv(ipListPath+"ipBlackList.txt", sep=" ", header=0)
        blacklist = blacklist.loc[blacklist['ip'] != IP]
        blacklist.to_csv(ipListPath + "ipBlacklist.txt", header=["ip"], sep=" ", index=None)

    return HttpResponse(status=200)

@api_view(['GET', 'POST'])
def validateRiseParticipant(request):
    """
    NB: The URI is not decoded in this process, so remains in the correct form for making the validation GET request to RISE
    """
    if request.method == "GET":
        data = {
            "id" : request.query_params.get("id"),
            "tag" : request.query_params.get("tag"),
            "iv" : request.query_params.get("iv"),
            "email" : request.query_params.get("email")
        }

        # Send data to rise:
        print("Validating URL:", "https://apply.risefortheworld.org/verify_roomworld?id=%s&tag=%s&iv=%s&email=%s" % (data["id"], data["tag"], data["iv"], data["email"]))
        x = requests.get("https://apply.risefortheworld.org/verify_roomworld", params=data ,auth = ('admin', 'angular-curse-both'))
        if x.status_code == 422 or x.status_code == "422":
            # Well actually we dont want a 422 - So filter this out another way
            print("422 Attempt invalid")
            return HttpResponse(x.reason, status=x.status_code)
        elif x.status_code == 401 or x.status_code == 403:
            print("Error accessing RISE server")
            return HttpResponse(status=x.status_code)
        elif str(x.status_code) == "200":
            # We can just do the email comparison here in the view
            riseData = x.json()
            if riseData["email"] == data["email"].replace("%40", "@"):
                print("success")
                return Response(x.json())
            else:
                return HttpResponse(status=401)
        else:
            return HttpResponse(status=x.status_code)

def effugiumView(request):

    reqIp = request.META.get("REMOTE_ADDR")
    # allowed = monitorIp(reqIp)
    allowed = True

    if allowed:
        return render(request, 'effugium.html', context={})
    else:
        return HttpResponse("<p>Too many access attempts, page access has been blocked. - Think this was a mistake? Contact support@risefortheworld.org</p>", status=403)

@api_view(['POST'])
def getExptDataView(request):
    """
    Summary:
            - Receive saved data from the game
    """

    if request.method == "POST":  
        # Reframe this to actually capture what ID might be
        # If we get an empty ID, assign a prolific ID - rise will always come with one
        if request.data.get("userId") == '':
            userId = "000" + str(random.randint(0, 99999999999))
        else:
            userId = request.data.get("userId")
        playerObj, created = RawLevelData.objects.get_or_create(userId = userId)
        urlP = json.loads(request.data.get('urlParameters'))
        # Encode URL parameters and remove email address
        for entry in urlP:
            if urlP[entry] is None:
                pass
            else:
                urlP[entry] = urllib.parse.quote(urlP[entry])
        # Remove email field
        urlP.pop("email")
        # Save
        playerObj.urlParameters = urlP

        startTime = json.loads(request.data.get("edata"))["exp_starttime"]
        if playerObj.rawData is None:
            playerObj.rawData = json.dumps({})
            playerObj.save()
        
        rawDataArray = json.loads(playerObj.rawData)
        rawDataArray[str(startTime)] = {
            "sdata" : request.data.get("sdata"),
            "edata" : request.data.get("edata"),
            "parameters" : request.data.get("parameters")
        }

        playerObj.rawData = json.dumps(rawDataArray)
        playerObj.userIP = request.META.get("REMOTE_ADDR")
        playerObj.save()

    return Response(userId)

@api_view(['POST'])
def confirmComplete(request):
    if request.method == "POST":
        data = {
            "startTime" : request.data.get("startTime"),
            "endTime" : request.data.get("endTime"),
            "hasCompleted" : request.data.get("hasCompleted")
        }
        print(data)

    # post complete to RISE
    rawRiseData = request.data.get("riseData")
    rawRiseDataJson = json.loads(rawRiseData)
    data = {
            "id" : rawRiseDataJson["id"],
            "tag" : rawRiseDataJson["tag"],
            "iv" : rawRiseDataJson["iv"],
            "email" : rawRiseDataJson["email"]
        }
    # print("For RISE:", data)
    print("Confirming completion:", "https://apply.risefortheworld.org/verify_roomworld?id=%s&tag=%s&iv=%s&email=%s" % (urllib.parse.quote(data["id"]), urllib.parse.quote(data["tag"]), urllib.parse.quote(data["iv"]), urllib.parse.quote(data["email"])))
    # urllib.parse.quote()

    x = requests.post("https://apply.risefortheworld.org/verify_roomworld?id=%s&tag=%s&iv=%s&email=%s" % (urllib.parse.quote(data["id"]), urllib.parse.quote(data["tag"]), urllib.parse.quote(data["iv"]), urllib.parse.quote(data["email"])), data=data, auth = ('admin', 'angular-curse-both'))
    print(x.status_code)
    if x.status_code == 422 or x.status_code == "422":
        print("Attempt invalid")
        return HttpResponse(status=x.status_code)
    elif x.status_code == 401 or x.status_code == 403:
        print("Error accessing RISE server")
        return HttpResponse(status=x.status_code)
    else:
        return HttpResponse(status=200)

@api_view(['GET'])
def testRiseEndpoint(request):
    if request.method == "GET":
        data = {
            "id" : request.data.get("id"),
            "tag" : request.data.get("tag"),
            "iv" : request.data.get("iv")
        }
        
    return Response({
        "error": False,
        "user_id" : "85",
        "email":"someEmail@email.com",
        "env" : "staging"
    })

@api_view(['GET'])
def dumpData(request, type):
    # Allowed types are `all`, `rise`, and `prolific`

    if request.user.is_authenticated:

        if request.method == "GET":
            # Get all data from DB and package nicely as JSON
            if type == "all":
                qs = RawLevelData.objects.all()
                qs_json = serializers.serialize('json', qs)
                return HttpResponse(qs_json, content_type="application/json")
            elif type == "prolific":
                qs == RawLevelData.objects.filter(userId__startswith='000')
                qs_json = serializers.serialize('json', qs)
                return HttpResponse(qs_json, content_type="application/json")
            elif type == "rise":
                qs == RawLevelData.objects.filter(userId__endswith="=")
                qs_json = serializers.serialize('json', qs)
                return HttpResponse(qs_json, content_type="application/json")
            else:
                return Response("Query type not known", status=404)
    else:
        return Response(status=401)

@api_view(['POST'])
def queryDB(request):
    # curl --user alex:<password> -X POST http://127.0.0.1:8000/effugium/queryDB/

    if request.method == "POST":
        data = {
            "population" : request.data.get("population"),
            "timescale" : request.data.get("timescale"),
            "datatype" : request.data.get("datatype"),
            "isComplete" : request.data.get("isComplete")
        }
        # Filter by population type
        if data["population"] == "rise":
            qs = RawLevelData.objects.filter(~Q(userId__startswith="000") & ~Q(userId__istartswith="RISE") & Q(userId__iregex=r'^.{7,}$') & ~Q(userIP="129.67.14.254") & ~Q(userIP="158.106.213.34"))
        elif data["population"] == "prolific":
            qs = RawLevelData.objects.filter(Q(userId__startswith="000") | Q(userId__istartswith="RISE"))
        else:
            qs = RawLevelData.objects.all()

        isComplete = True if data["isComplete"] == "complete" else False
        if data["datatype"] == "round":
            dbData, numComplete = formatByRound(qs, isComplete)
        elif data["datatype"] == "response":
            dbData = formatByResponse(qs, isComplete)

        # Pickle locally
        if platform.uname().system == "Windows":
            path = ("tmp/%s_%s.csv" % (str(int(time.time())), data["datatype"] ))
            df = pd.DataFrame.from_dict(dbData, orient="index")
            df.to_csv(path)
            userMsg = "Your data is available at " + path
        elif platform.uname().system == "Linux":
            try:
                print("Saving file")
                path = ("home/alex/backups/data/%s_%s.csv" % (str(int(time.time())), data["datatype"] ))
                df = pd.DataFrame.from_dict(dbData, orient="index")
                df.to_csv(path)
                print("Voila")
            except Exception as e:
                print(traceback.format_exc())
            userMsg = "Your data is available at " + path
        print("Made it to this point")

        if request.user.is_authenticated:
            # return HttpResponse(json.dumps(roundData), content_type='text/csv')
            return HttpResponse(userMsg)
        else:
            return Response(status=403)
    else:
        return Response("Query type not accepted", status=403)

def getQueryDataView(request):

    # Query for all RISE data, pass it through the formatByRound() function, and output some stats
    qs = RawLevelData.objects.filter(~Q(userId__startswith="000") & ~Q(userId__istartswith="RISE") & Q(userId__iregex=r'^.{7,}$') & ~Q(userIP="129.67.14.254") & ~Q(userIP="158.106.213.34"))
    # Save raw queryset
    serializer = RawLevelDataSerializer(qs, many=True)
    qsJson = JSONRenderer().render(serializer.data)

    with open(f'tmp/{int(datetime.now().timestamp())}.pickle', 'wb') as handle:
        pickle.dump(qsJson, handle)
    # roundData, numComplete = formatByRound(qs, speed=True)

    context = {
        "numPlayers" : len(qs),
        "numComplete" : 0,
        "pctComplete" : 0 if len(qs)==0 else round((0/len(qs))*100, 2)
    }

    return render(request, 'effugiumData.html', context)

def formatByRound(qs, completedOnly=False, speed=False):
    """
    Summary:
            - Take in queryset and return in round-by-round format
    
    dict_keys(['expt_index', 'expt_trial', 'trial_layout', 'trial_level', 'trial_solved', 'trial_attempts', 'trial_game', 
                'trial_transfer', 'trial_test', 'game', 'game_solved', 'game_layout', 'game_level', 'game_attempts', 
                'game_transfer', 'game_test', 'test_index', 'test_solved', 'test_layout', 'RPM', 'attempted_layouts', 'resp'])
    """
    count = 0
    data = {}
    numComplete = 0
    for game in qs:
        playerTrials = json.loads(game.rawData)
        playerId = game.userId
        # Within playerTrials we have all this individual players' attempts.
        # We just want the first one where edata.gameCompleted is true

        # Get all the timestamp keys:
        timestamps = list(playerTrials.keys())
        gotCompletedGame = False
        for t in timestamps:
            hasCompleted = json.loads(playerTrials[t]['edata'])['gameCompleted']
            # If completed, this is the data we store:
            if hasCompleted:
                gotCompletedGame = True
                numComplete += 1
                try:
                    sdata = json.loads(playerTrials[t]['sdata'])
                except:
                    sdata = {}
                for i in range(len(sdata["expt_index"])):
                    if len(sdata["resp"][str(i)]["xloc"]) == 0 or len(sdata["resp"][str(i)]["yloc"]) == 0:
                        lastRoom = []
                    else:
                        lastRoom = [int(sdata["resp"][str(i)]["xloc"][-1])%4, int(sdata["resp"][str(i)]["yloc"][-1])%4]
                        # lastRoom = [(sdata["resp"][str(i)]["xloc"][-1]-1)%3, (sdata["resp"][str(i)]["yloc"][-1]-1)%3]
                    try:
                        data[str(count)] = {
                            "id" : playerId,
                            "iv" : None if game.urlParameters is None else game.urlParameters["iv"],
                            "tag" : None if game.urlParameters is None else game.urlParameters["tag"],
                            "pk" : game.pk,
                            "expt_index" : sdata["expt_index"][i],
                            "expt_trial" : sdata["expt_trial"][i],
                            "trial_layout" : sdata["trial_layout"][i],
                            "trial_level" : sdata["trial_level"][i],
                            "trial_solved" : sdata["trial_solved"][i],
                            "trial_attempts" : sdata["trial_attempts"][i],
                            "trial_game" : sdata["trial_game"][i],
                            "trial_transfer" : sdata["trial_transfer"][i],
                            "trial_test" : sdata["trial_test"][i],
                            "round_start_time" : sdata["resp"][str(i)]["timestamp"][0] - sdata["resp"][str(i)]["reactiontime"][0],
                            "round_end_time" : sdata["resp"][str(i)]["timestamp"][-1],
                            "last_room" : lastRoom,
                            "complete" : gotCompletedGame,
                            # "last_room" : [(sdata["resp"][str(i)]["xloc"][-1]-1)%3, (sdata["resp"][str(i)]["yloc"][-1]-1)%3] if (len(sdata["resp"][str(i)]["xloc"]) !=0 and len(sdata["resp"][str(i)]["yloc"]) != 0) else [],
                        }
                    except Exception as e:
                        print(playerId, sdata["resp"][str(i)])
                        print(traceback.format_exc())
                    count += 1
                # Break out since we only want the first completed instance
                break
            
        if not gotCompletedGame and not completedOnly:
            # Have never received a completed game
            t = timestamps[0]
            sdata = json.loads(playerTrials[t]['sdata'])
            for i in range(len(sdata["expt_index"])):
                if len(sdata["resp"][str(i)]["xloc"]) == 0 or len(sdata["resp"][str(i)]["yloc"]) == 0:
                    lastRoom = [-1, -1]
                else:
                    lastRoom = [int(sdata["resp"][str(i)]["xloc"][-1])%4, int(sdata["resp"][str(i)]["yloc"][-1])%4]
                    # lastRoom = [(sdata["resp"][str(i)]["xloc"][-1]-1)%3, (sdata["resp"][str(i)]["yloc"][-1]-1)%3]
                try:
                    data[str(count)] = {
                        "id" : playerId,
                        "iv" : None if game.urlParameters is None else game.urlParameters["iv"],
                        "tag" : None if game.urlParameters is None else game.urlParameters["tag"],
                        "pk" : game.pk,
                        "expt_index" : sdata["expt_index"][i],
                        "expt_trial" : sdata["expt_trial"][i],
                        "trial_layout" : sdata["trial_layout"][i],
                        "trial_level" : sdata["trial_level"][i],
                        "trial_solved" : sdata["trial_solved"][i],
                        "trial_attempts" : sdata["trial_attempts"][i],
                        "trial_game" : sdata["trial_game"][i],
                        "trial_transfer" : sdata["trial_transfer"][i],
                        "trial_test" : sdata["trial_test"][i],
                        "round_start_time" : sdata["resp"][str(i)]["timestamp"][0] - sdata["resp"][str(i)]["reactiontime"][0],
                        "round_end_time" : sdata["resp"][str(i)]["timestamp"][-1],
                        "last_room" : lastRoom,
                        "complete" : gotCompletedGame,
                        # "last_room" : [(sdata["resp"][str(i)]["xloc"][-1]-1)%3, (sdata["resp"][str(i)]["yloc"][-1]-1)%3] if (len(sdata["resp"][str(i)]["xloc"]) !=0 and len(sdata["resp"][str(i)]["yloc"]) != 0) else [],
                    }
                except Exception as e:
                        print(playerId, sdata["resp"][str(i)]["timestamp"], sdata["resp"][str(i)]["reactiontime"])
                        print(traceback.format_exc())
                count += 1
    print("Done!")
    return data, numComplete

def formatByResponse(qs, completedOnly=False):
    """
    Summary:
            - Take in queryset and return in response-by-response format
    """    
    
    count = 0
    data = {}
    for game in qs:
        playerTrials = json.loads(game.rawData)
        playerId = game.userId
        # Within playerTrials we have all this individual players' attempts.
        # We just want the first one where edata.gameCompleted is true

        # Get all the timestamp keys:
        timestamps = list(playerTrials.keys())
        gotCompletedGame = False
        for t in timestamps:
            hasCompleted = json.loads(playerTrials[t]['edata'])['gameCompleted']
            # If completed, this is the data we store:
            if hasCompleted:
                gotCompletedGame = True
                sdata = json.loads(playerTrials[t]['sdata'])
                responses = sdata['resp']
                for r in responses:
                    for i in range(len(responses[r]['timestamp'])):
                        data[str(count)] = {
                            "id" : playerId,
                            "pk" : game.pk,
                            "timestamp" : responses[r]['timestamp'][i],
                            "reactiontime" : responses[r]['reactiontime'][i],
                            "direction" : responses[r]['direction'][i],
                            "allowed" : responses[r]['allowed'][i],
                            "tool" : responses[r]['tool'][i],
                            "xloc" : responses[r]['xloc'][i],
                            "yloc" : responses[r]['yloc'][i]
                        }
                        count += 1
                # Break out since we only want the first completed instance
                break

        if not gotCompletedGame and not completedOnly:
            t = timestamps[0]
            sdata = json.loads(playerTrials[t]['sdata'])
            responses = sdata['resp']
            for r in responses:
                for i in range(len(responses[r]['timestamp'])):
                    data[str(count)] = {
                        "id" : playerId,
                        "pk" : game.pk,
                        "timestamp"     :    responses[r]['timestamp'][i],
                        "reactiontime"  :    responses[r]['reactiontime'][i],
                        "direction"     :    responses[r]['direction'][i],
                        "allowed"       :    responses[r]['allowed'][i],
                        "tool"          :    responses[r]['tool'][i],
                        "xloc"          :    responses[r]['xloc'][i],
                        "yloc"          :    responses[r]['yloc'][i]
                    }
                    count += 1

    return data