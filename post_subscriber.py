import pprint
import random
import re
import requests

#url for my testing app - for some reason this never shows in my app dashboard so i have to save a link here...
#https://streamlabs.com/dashboard#/oauth-clients/5425

#i get the code below from:
#https://streamlabs.com/api/v2.0/authorize?client_id=9b488784-8c91-4577-a666-496937459254&redirect_uri=http://localhost&scope=alerts.write+alerts.create&response_type=code&state=123456

#get access_token flow:

try_it_url = ""
code = re.search("http://localhost/\?code=(.*)&.*", try_it_url).group(1)
url = "https://streamlabs.com/api/v2.0/token"

headers = {"accept": "application/json"}

payload = {
    "grant_type": "authorization_code",
    "client_id": "CHANGEME",
    "client_secret": "CHANGEME",
    "redirect_uri": "http://localhost",
    "code": code
}

response = requests.post(url, json=payload, headers=headers)
access_token = response.json()["access_token"]
pprint.pprint(response.json())

#post donation flow
url = "https://streamlabs.com/api/v2.0/donations"

name = "I Wake Up Hungry"
name = name.replace("&", "and")
name = name.replace("-", " ")
name = name.replace(".", " ")


if len(name) > 25:
    name = name[0:25]

payload = {
    "name": name,
    "message": "New Subscriber",
    "identifier": "outside_live_stream",
    "amount": random.randint(1,100),
    "currency": "usd",
}
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": f"Bearer {access_token}"
}
print(headers)
print(payload)
response = requests.post(url, json=payload, headers=headers)
print(response.text)

#Always 401 Unauthorized