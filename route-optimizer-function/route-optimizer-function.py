## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0

import json
import boto3
import os

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from math import radians, cos, sin, asin, sqrt

location = boto3.client('location')

#Name Location Resources (Values Created and Passed at SAM Deployment)
location_place_index = os.environ.get('LOCATION_PLACE_INDEX')
location_route_calculator = os.environ.get('LOCATION_ROUTE_CALCULATOR')

#Define parameters for API (Values Passed from API)
DistanceUnit = 'Miles' #takes 'Miles' or 'Kilometers'
TravelMode = 'Car' #takes 'Car', 'Truck', or 'Walking'
optimize_for = 'DurationSeconds'


def lambda_handler(event, context):
    event = json.loads(event['body'])

    print("Event Data:", event)
    #Get event data for Travel Mode (Walking, Car, or Truck)
    if "travel_mode" in event:
        TravelMode = event["travel_mode"]
    #Get event data for optimize for (Distance or Duration)
    if "optimize_for" in event:
        optimize_for = event["optimize_for"]
    points = []
    #Get coordinate pair from event data
    for coordiante_pair in event["coordinates"]:
        coordinate_pair = tuple(coordiante_pair)
        points.append(coordinate_pair)
    
    coordinates = []
    labels = []
    #get address of each coordinate 
    for item in points:
        response = location.search_place_index_for_position(
            IndexName=location_place_index,
            Position=item)
        json_response = response["Results"]
        point = (json_response[0]["Place"]["Geometry"]["Point"][0:2])
        label = (json_response[0]["Place"]["Label"])
        coordinates.append(point)
        labels.append(label)
    
    result = [item for sublist in zip(labels, coordinates) for item in sublist]
   
    payload = result
    num_locations = int((len(payload) / 2))
    place_names = payload[0:num_locations*2:2]
    coordinates = payload[1:num_locations*2:2]
    points = []
    #Create an empty list for the shortest route
    shortest_route = []
    starting_node = 0
    
    def decode_list(coordinates):
        for i in coordinates:
            y = tuple(i)
            points.append(y)
    
    # Define the Flatten/Unflatten fucntions used in building the distance matrix
    def flatten_list(t):
        return [item for sublist in t for item in sublist]
    
    def unflatten_list(l, n):
        # looping till length l
        for i in range(0, len(l), n):
            yield l[i:i + n]
    
        # function used to create distance matrix using calculate_route_matrix from Amazon Location Service, returning travel distances between each node
    def build_distance_matrix(shipments, measure='distance'):
        origins = destinations = points
        
        print("calling Location Services")
        
        try:
            dm_response = location.calculate_route_matrix(
                CalculatorName=location_route_calculator,
                DeparturePositions=origins,
                DestinationPositions=destinations,
                TravelMode=TravelMode,
                DistanceUnit=DistanceUnit)
            
            print("raw response",dm_response) 
        except Exception as e:
            print(e)
        
        dm_raw = (dm_response['RouteMatrix'])
        dm_flat = flatten_list(dm_raw)
        print("Optimize For:", optimize_for)
        dm_flattened = [d[optimize_for] for d in dm_flat]
        distance_matrix = list(unflatten_list(dm_flattened, num_locations))
        return distance_matrix
    
        ## function to converted final optimized route into place names
        
    def approx_distance_haversine(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance in kilometers between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 3956 
        return c * r

    def build_distance_matrix_v2(positions):
        dmatrix = []
        for i in positions:
            nmatrix=[]
            for j in positions:
                nmatrix.append(approx_distance_haversine(i[0],i[1],j[0],j[1]))
            dmatrix.append(nmatrix)
        
        return dmatrix
    
    def label_nodes(i):
        
        for x in i:
            shortest_route.append(place_names[x])
            shortest_route.append(points[x])
        
        
        shortest_route.append(place_names[0])
        shortest_route.append(points[0])
        
        #print(shortest_route)
        return shortest_route

        # implementation of traveling Salesman Problem
    
    def get_solution(manager, routing, solution):
        """Prints solution on console."""
        print('Objective: {}'.format(solution.ObjectiveValue()))
        index = routing.Start(0)
        plan_output = 'Route:\n'
        route_distance = 0
        nodes=[index]
        while not routing.IsEnd(index):
            plan_output += ' {} ->'.format(manager.IndexToNode(index))
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            nodes.append(index)
            route_distance += routing.GetArcCostForVehicle(previous_index, index, 0)
        plan_output += ' {}\n'.format(manager.IndexToNode(index))
        print(plan_output)
        plan_output += 'Objective: {}m\n'.format(route_distance)
    
        return nodes, plan_output,route_distance


    def solve(num_locations, graph, starting_node):
        from ortools.constraint_solver import pywrapcp
        # Create the routing index manager.
        manager = pywrapcp.RoutingIndexManager(num_locations, 1, starting_node) # for VSP, num vehicles is 1
    
        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)
    
        distance_matrix = graph
    
        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            # Convert from routing variable Index to distance matrix NodeIndex.
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]
    
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    
        # Define cost of each arc.
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)
        print(solution)
    
        # Print solution on console.
        if solution:
            return get_solution(manager, routing, solution)
        else:
            return "no solution found"

        
    def solve_for_traveling_salesperson_v2(num_locations, graph, starting_node):
        print(graph)
        try:
            nodes, plan_output,min_path = solve(num_locations,graph, starting_node)
        except Exception as e:
            print("in v2 solve")
            print(e)
        return (min_path), label_nodes(nodes[0:-1])
        
    
    def solve_for_traveling_salesperson(graph, starting_node):
        # store all vertex apart from source vertex
        nodes = []
        for node in range(num_locations):
            if node != starting_node:
                nodes.append(node)
          
            # store minimum weight Hamiltonian Cycle
        min_path = maxsize
    
        next_permutation = permutations(nodes)
        for items in next_permutation:
            # store current Path weight(cost)
            current_pathweight = 0
            # compute current path weight
            x = starting_node
            for item in items:
                current_pathweight += distance_matrix[x][item]
                x = item
            current_pathweight += distance_matrix[x][starting_node]
            min_path = min(min_path, current_pathweight)
            # set current shortest route (optimized_route)
            if current_pathweight == min_path:
                optimized_route = items
        return (min_path), label_nodes(optimized_route)
    
        ### Execute funtions
    try:
        decode_list(coordinates)
        
    except:
        print('Something went wrong decoding coordinates')
    try:
        # distance_matrix = build_distance_matrix(points) # Esri - 10, Here - 350 limit for locations
        location_service_matrix = build_distance_matrix(points)#build_distance_matrix_v2(points)
        print("Routes Calculated Using Distance Matrix From Amazon Location Service")
    
    except: 
        location_service_matrix = build_distance_matrix_v2(points)
        print("Routes Calculated Using Haversine Approximate Estimate for Distance Matrix")
    
    try: 
        # solution = solve_for_traveling_salesperson(distance_matrix, starting_node)
        solution = solve_for_traveling_salesperson_v2(num_locations,location_service_matrix, starting_node)
   
    
    except Exception as e:
        print(e)
        solution=(e,0)
        print('Could not find the Optimal Route')
    
    ### Calculate route Using the results of the traveling salesperson function, with ordered waypoints specific to the optimized route
    locations = solution[1]
    coordinates = locations[1:num_locations*2:2]
    points = []
    if num_locations < 23:
        try:
            response1 = location.calculate_route(
                CalculatorName=location_route_calculator,
    # Optionally add CarMode Options Here
                # CarModeOptions={
                #     'AvoidFerries': False,
                #     'AvoidTolls': False
                # },
                DepartNow=True,
                DeparturePosition=[
                    coordinates[0][0], coordinates[0][1]
                ],
    # Optionally add Departure Time Here
                # DepartureTime=datetime(2015, 1, 1),
                DestinationPosition=[coordinates[0][0], coordinates[0][1]],
                DistanceUnit=DistanceUnit,
                IncludeLegGeometry=True,
                TravelMode=TravelMode,  # |'Truck'|'Walking',
                WaypointPositions=coordinates[1:23]
            )
            print(num_locations, "Waypoints")
            
            body = json.dumps({
                'summary': json.dumps(response1["Summary"]), ####Need to Fix
                'minimum_weight_path': json.dumps(solution), ####Need to Fix
                'waypoints': json.dumps(response1["Legs"])}
            )
            
            response = {
            'statusCode': 200,
            'body': body
            }
    # Ensure that this function can be called from wherever you want to (CORS headers).
            response["headers"] = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
            }
    # Return the response object.
            return response
          
        except Exception as e:
            print(e)
            return {
            'statusCode': 501,
            'summary': e,
            'minimum_weight_path': 0,
            }
    
    if num_locations >= 23:
        try:
            response2 = location.calculate_route(
                    CalculatorName=location_route_calculator,
    # Optionally Add Car Mode Options               
                    # CarModeOptions={
                    #     'AvoidFerries': False,
                    #     'AvoidTolls': False
                    # },
                    DepartNow=True,
                    DeparturePosition=[
                        coordinates[0][0], coordinates[0][1]
                    ],
    # Optionally Add Departure Time Here
                    #DepartureTime=datetime(2015, 1, 1),
                    DestinationPosition=[coordinates[22][0], coordinates[22][1]],
                    DistanceUnit=DistanceUnit,
                    IncludeLegGeometry=True,
                    TravelMode=TravelMode,  # |'Truck'|'Walking',
                    WaypointPositions=coordinates[1:22]
            )
                
            response3 = location.calculate_route(
                    CalculatorName=location_route_calculator,
    # Optionally Add Car Modes Here
                    # CarModeOptions={
                    #     'AvoidFerries': False,
                    #     'AvoidTolls': False
                    # },
                    DepartNow=True,
                    DeparturePosition=[
                        coordinates[22][0], coordinates[22][1]
                    ],
    # Optionally Add Departure Time Here                   
                        # DepartureTime=datetime(2015, 1, 1),
                    DestinationPosition=[coordinates[0][0], coordinates[0][1]],
                    DistanceUnit=DistanceUnit,
                    IncludeLegGeometry=True,
                    TravelMode=TravelMode,  # |'Truck'|'Walking',
                    WaypointPositions=coordinates[22:46]
            )
            
    # Convert both outputs from calculate route into a single output (Work in Progress)
            legsa = json.dumps(response2["Legs"])
            legsa = legsa[1:-1] + ','
            legsb = json.dumps(response3["Legs"])
            legsb = legsb[1:-1]
    # NEED TO ADD LOGIC TO REPORT SUMMARY and MWHC
            merged_dict = (str(legsa)+str(legsb))
            merged_dict = "[" + merged_dict + "]"
            print(num_locations, "Waypoints")
            
            body = json.dumps({
                'summary': json.dumps(response2["Summary"]), ####Need to Fix
                'minimum_weight_path': json.dumps(solution), ####Need to Fix
                'waypoints': merged_dict}
            )
            
            response = {
            'statusCode': 200,
            'body': body
            }
    # Ensure that this function can be called from wherever you want to (CORS headers).
            response["headers"] = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
            }
    # Return the complete response object.
            return response
    
        except Exception as e:
            print(e)
            return {
            'statusCode': 501,
            'summary': e,
            'minimum_weight_path': 0,
            }
