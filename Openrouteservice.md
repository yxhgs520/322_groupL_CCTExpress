Openrouteservice

Introduction
This is the openrouteservice API documentation for ORS Core-Version 9.3.0. 

Authentication
User Security
Query-Parameter: For GET requests add your API Key as the value of the `api_key` parameter or use the Authorization-Header.
Authorization-Header: For POST & GET requests add your API Key as the value of the `Authorization` header.


##Directions Service
Get directions for different modes of transport

/v2/directions/{profile}
GET Directions Service
Get a basic route between two points with the profile provided. Returned response is in GeoJSON format. This method does not accept any request body or parameters other than profile, start coordinate, and end coordinate.

```EXAMPLE CODE (PYTHON):

import requests

headers = {
    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
}
call = requests.get('https://api.openrouteservice.org/v2/directions/driving-car?api_key=your-api-key&start=8.681495,49.41461&end=8.687872,49.420318', headers=headers)

print(call.status_code, call.reason)
print(call.text)
```
RESPONSES

|Status|Description|
|:-|:-|
|200|Standard response for successfully processed requests. Returns GeoJSON.|
|400|The request is incorrect and therefore can not be processed.|
|404|An element could not be found. If possible, a more detailed error code is provided.|
|405|The specified HTTP method is not supported. For more details, refer to the EndPoint documentation.|
|413|The request is larger than the server is able to process, the data provided in the request exceeds the capacity limit.|
|500|An unexpected error was encountered and a more detailed error code is provided.|
|501|Indicates that the server does not support the functionality needed to fulfill the request.|
|503|The server is currently unavailable due to overload or maintenance.|



/v2/directions/{profile}/json
POST Directions Service JSON
Authorization-Header

Returns a route between two or more locations for a selected profile and its settings as JSON

```EXAMPLE CODE (PYTHON):
import requests

body = {"coordinates":[[8.681495,49.41461],[8.686507,49.41943],[8.687872,49.420318]]}

headers = {
    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
    'Authorization': 'your-api-key',
    'Content-Type': 'application/json; charset=utf-8'
}
call = requests.post('https://api.openrouteservice.org/v2/directions/driving-car/json', json=body, headers=headers)

print(call.status_code, call.reason)
print(call.text)
```
