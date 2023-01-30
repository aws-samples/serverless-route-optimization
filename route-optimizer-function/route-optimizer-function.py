## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0

import json
import boto3
import os
from datetime import datetime
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

##from math import radians, cos, sin, asin, sqrt

location = boto3.client('location')

#Name Location Resources (Values Created and Passed at SAM Deployment)
location_place_index = os.environ.get('LOCATION_PLACE_INDEX')
location_route_calculator = os.environ.get('LOCATION_ROUTE_CALCULATOR')

#Define parameters for default API Values (Dynamic Values Passed from APIGW on each invokation, updated in lambda_handler)
DistanceUnit = 'Miles' #takes 'Miles' or 'Kilometers'
TravelMode = 'Car' #takes 'Car', 'Truck', or 'Walking'
optimize_for = 'Distance'

def lambda_handler(event, context):
    event = json.loads(event['body'])
    print("Event Data:", event)
    
    #######################################################
    ### Get event data for user inputs from API Gateway ###
    #######################################################
    if "travel_mode" in event:
        TravelMode = event["travel_mode"] ### takes Walking, Car, or Truck
    if "optimize_for" in event:
        optimize_for = event["optimize_for"] ### takes Distance or Duration
    else: 
        optimize_for = 'Distance'
    if "num_vehicles" in event:
        num_vehicles = int(event["num_vehicles"]) ### takes value 1 - 10
    else:
        num_vehicles = 1
    if len(event["departure_time"]) > 0:
        time_of_day = event["departure_time"]
        print("TYPE Given", type(time_of_day))
    else:
        time_of_day = datetime.now()
        print("TYPE AUTO", type(time_of_day))
        
    if "delivery_per_vehicle" in event:
        delivery_per_vehicle = int(event["delivery_per_vehicle"]) ### takes value 1 - 15
    else: 
        delivery_per_vehicle = 3
    if "max_route_length" in event:
        max_route_length = int(event["max_route_length"])*1000
    else: 
        max_route_length = 5000
    
    ###Extra Feature:
    if "balance_route_length" in event:
        balance_route_length = int(event["balance_route_length"])
    else: 
        balance_route_length = 100
    
    #balance_route_length = global balance_route_length
    print("BALANCE1", balance_route_length)
    #print("MAX", max_route_length)
    
    DistanceUnit = 'Miles' ### takes 'Miles' or 'Kilometers' 
    #print(time_of_day)
    
    ###########################
    ### Data Pre-Processing ###
    ###########################
    starting_node = 0    
    points = []
    plan_nodes = []
    ### Get coordinate pair from event data
    for coordiante_pair in event["coordinates"]:
        coordinate_pair = tuple(coordiante_pair)
        points.append(coordinate_pair)
    print("POINTS1:", points)
    points = points[::2]
    print("POINTS:", points)
    
    coordinates = []
    labels = []
    
    ### get address of each coordinate using Places API 
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
   
    num_locations = int((len(result) / 2))
    place_names = result[0:num_locations*2:2]
    coordinates = result[1:num_locations*2:2]
    
    ######################################################################################################
    ### Functions to build a distance matrix using calculate_route_matrix from Amazon Location Service ###
    ###                              Returns travel distances between each node                        ###
    ######################################################################################################
    def send_request():
        origins = destinations = points
        # print("calling Location Services")
        try:
            dm_response = location.calculate_route_matrix(
                CalculatorName=location_route_calculator,
                DeparturePositions=origins,
                DestinationPositions=destinations,
                TravelMode=TravelMode,
                DepartureTime=time_of_day,
                DistanceUnit=DistanceUnit)
            return dm_response
        except Exception as e:
             print(e)
             
    def build_matrix(dm_response):
        graph = []
        for row in dm_response['RouteMatrix']:
            row_list = [int(row[j][optimize_for] * 1000) for j in range(len(row))]
            graph.append(row_list)
        return(graph)
    
    def create_distance_matrix(points):
        response = send_request()
        distance_matrix = build_matrix(response)
        return(distance_matrix)
    
    def create_data_model():
        data = {}
        data['distance_matrix'] = create_distance_matrix(points)
        data['num_vehicles'] = num_vehicles
        data['depot'] = 0
        print(data)
        return data
    
    def print_solution(data, manager, routing, solution):
        max_route_distance = 0
        all_vehicle_routes = {}
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
            route_distance = 0
            all_vehicle_routes[vehicle_id]={'nodes':[index]}
            while not routing.IsEnd(index):
                plan_output += ' {} -> '.format(manager.IndexToNode(index))
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                all_vehicle_routes[vehicle_id]['nodes'].append(index)
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id)
            
            plan_output += '{}\n'.format(manager.IndexToNode(index))
            all_vehicle_routes[vehicle_id]['plan_output'] = plan_output
            max_route_distance = max(route_distance, max_route_distance)
            all_vehicle_routes[vehicle_id]['route_distance']=route_distance
            all_vehicle_routes[vehicle_id]['nodes'][0]=0
            all_vehicle_routes[vehicle_id]['nodes'][-1]=0
        
        print('Maximum of the route distances: {}m'.format(max_route_distance))
        return(all_vehicle_routes)
    

    def main():
        # Create the routing index manager.
        from ortools.constraint_solver import pywrapcp
        manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                               data['num_vehicles'], data['depot'])
    
        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)
    
        # Create and register a transit callback. Returns the distance between 2 nodes
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data['distance_matrix'][from_node][to_node]
        
        # def counter_callback(from_index):
        #     """Returns 1 for any locations except depot."""
        #     # Convert from routing variable Index to user NodeIndex.
        #     from_node = manager.IndexToNode(from_index)
        #     return 1 if (from_node != 0) else 0; 
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        # Define cost of each arc.
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
        # Add Distance constraint.
        dimension_name = 'Distance'
        routing.AddDimension(
            transit_callback_index,
            0,  # no slack
            max_route_length,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name)
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(balance_route_length)
        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)
        # Print solution on console.
        if solution:
            vehicle_output = print_solution(data, manager, routing, solution)
            return(vehicle_output)
        else:
            print('No solution found !')

    def route_vehicles(): #num_locations, distance_matrix, starting_node, num_vehicles):
        all_vehicle_routes = main()
        return(all_vehicle_routes)
        print("all_vehicle_routes:",all_vehicle_routes)
        
    def solve_for_traveling_salesperson_v2(num_locations, distance_matrix, starting_node, num_vehicles):
        def label_nodes(i):
            shortest_route = []
            for x in i:
                shortest_route.append(place_names[x])
                shortest_route.append(points[x])
            shortest_route.append(place_names[0])
            shortest_route.append(points[0])
            print("Shortest Route:", shortest_route)
            return shortest_route
        try:
            all_vehicle_routes = main()
            voutput = {}
            for vid in range(num_vehicles):
                nodes = all_vehicle_routes[vid]['nodes']
                min_path = all_vehicle_routes[vid]['route_distance']
                #print(f"Vehicle id:{vid} with {len(nodes)-1} nodes")
                #print(min_path)
                voutput[vid] = (min_path), label_nodes(nodes[0:-1])
            print(voutput)
            return voutput
                
        except Exception as e:
            print("error in v2 solve")
            print(e)    
    
    data = create_data_model()   
    #print("DISTANCEMATRIX", distance_matrix)
    solution = solve_for_traveling_salesperson_v2(num_locations, data, starting_node, num_vehicles)
    
    print("Solution:", solution)


    ### Calculate route Using the results of the traveling salesperson function, with ordered waypoints specific to the optimized route
    allresponse = {}
    allresponse["headers"] = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
    }
   
    allsummary = {}
    alllegs = {}
    vehicle_output1 = solution
    for n in range(num_vehicles):
        locations = solution[n][1]
        coordinates = locations[1::2]
        points = []
        
        numfullsegments = int(len(coordinates)/23)
        numlastsegment = len(coordinates)%23
        
        legs=[]
        summary=[]
        starti=0
        endi=0
        for s in range(numfullsegments):
            
            starti = s*23
            endi = (s+1)*23
            
            response = location.calculate_route(
                CalculatorName=location_route_calculator,
                DepartNow=False,
                DepartureTime=time_of_day,
                DeparturePosition=[
                    coordinates[starti][0], coordinates[starti][1]
                ],
                DestinationPosition=[coordinates[endi-1][0], coordinates[endi-1][1]],
                DistanceUnit=DistanceUnit,
                IncludeLegGeometry=True,
                TravelMode=TravelMode,  # |'Truck'|'Walking',
                WaypointPositions=coordinates[starti+1:endi-1]
            )
            
            legs.append(response["Legs"])
            summary.append(response["Summary"])
        
        endi = max(endi,numlastsegment)
        allsummary[n] = summary
        alllegs[n] = legs
        
        response = location.calculate_route(
                CalculatorName=location_route_calculator,
                DepartNow=False,
                DepartureTime=time_of_day,
                DeparturePosition=[
                    coordinates[starti][0], coordinates[starti][1]
                ],
                DestinationPosition=[coordinates[endi-1][0], coordinates[endi-1][1]],
                DistanceUnit=DistanceUnit,
                IncludeLegGeometry=True,
                TravelMode=TravelMode,  
                WaypointPositions=coordinates[starti+1:endi-1]
            )
        
        alllegs[n].append(response["Legs"])
        allsummary[n].append(response["Summary"])
            
            
    if num_vehicles==1:
        body = {
                'summary': allsummary[0], 
                'minimum_weight_path': solution[0], 
                'waypoints': alllegs[0],
                'vehicle_output': vehicle_output1
        }

    else:
        body = {
                'summary': allsummary, 
                'minimum_weight_path': [solution[n][0] for n in range(num_vehicles)], 
                'waypoints': alllegs,
                'vehicle_output': vehicle_output1
                }
            
    ret =  {
        'statusCode': 200,
        'headers': {
                    "Access-Control-Allow-Origin" : "*"
                },
        'body': json.dumps(body)
        }
        
    print("Printing return value")
    print(ret)
    
    return ret

