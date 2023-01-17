## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0

import json
import boto3
import os
import datetime
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from math import radians, cos, sin, asin, sqrt

location = boto3.client('location')

#Name Location Resources (Values Created and Passed at SAM Deployment)
location_place_index = os.environ.get('LOCATION_PLACE_INDEX')
location_route_calculator = os.environ.get('LOCATION_ROUTE_CALCULATOR')

#Define parameters for default API Values (Dynamic Values Passed from APIGW on each invokation, updated in lambda_handler)
DistanceUnit = 'Miles' #takes 'Miles' or 'Kilometers'
TravelMode = 'Car' #takes 'Car', 'Truck', or 'Walking'
optimize_for = 'Distance'
# time_of_day = datetime.datetime.now()
# time_of_day = time_of_day.isoformat()

def lambda_handler(event, context):
    event = json.loads(event['body'])
    DistanceUnit = 'Miles' ### takes 'Miles' or 'Kilometers'
    print("Event Data:", event)
    
    #######################################################
    ### Get event data for user inputs from API Gateway ###
    #######################################################
    if "travel_mode" in event:
        TravelMode = event["travel_mode"] ### takes Walking, Car, or Truck
    if "optimize_for" in event:
        optimize_for = event["optimize_for"] ### takes Distance or Duration
    if "num_vehicles" in event:
        num_vehicles = int(event["num_vehicles"]) ### takes value 1 - 10
    else:
        num_vehicles = 1
    if "departure_time" in event:
        time_of_day = event["departure_time"]
    if "delivery_per_vehicle" in event:
        delivery_per_vehicle = int(event["delivery_per_vehicle"]) ### takes value 1 - 15
    else: 
        delivery_per_vehicle = 3
    print(time_of_day)
    
    ###########################
    ### Data Pre-Processing ###
    ###########################
    points = []
    plan_nodes = []
    all_vehicle_nodes = []
    ### Get coordinate pair from event data
    for coordiante_pair in event["coordinates"]:
        coordinate_pair = tuple(coordiante_pair)
        points.append(coordinate_pair)
    points = points[::2]
    print("POINTS:", points)
    
    coordinates = []
    labels = []
    ### Get address of each coordinate 
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
    starting_node = 0
    
    ########################################
    ### Define Data Processing Functions ###
    ########################################
    
    ### Define function to pre-process list of coordinates
    def decode_list(coordinates):
        for i in coordinates:
            y = tuple(i)
            points.append(y)
    
    ### Define the Flatten/Unflatten fucntions used in building the distance matrix
    def flatten_list(t):
        return [item for sublist in t for item in sublist]
    
    def unflatten_list(l, n):
        # looping till length l
        for i in range(0, len(l), n):
            yield l[i:i + n]
    
    ##########################################################################################################
    ### Function used to build a distance matrix using calculate_route_matrix from Amazon Location Service ###
    ###                              Returns travel distances between each node                            ###
    ##########################################################################################################
    def build_distance_matrix(shipments, measure='distance'):
        origins = destinations = points
        
        print("calling Location Services - calculate_route_matrix")

        try:
            dm_response = location.calculate_route_matrix(
                CalculatorName=location_route_calculator,
                DeparturePositions=origins,
                DestinationPositions=destinations,
                TravelMode=TravelMode,
                DistanceUnit=DistanceUnit)
            
            # print("raw response",dm_response) 
        except Exception as e:
            print(e)
            
        ### Process and reformat response 
        dm_raw = (dm_response['RouteMatrix'])
        print(dm_raw)
        dm_flat = flatten_list(dm_raw)
        dm_flattened = [d[optimize_for] for d in dm_flat]
        dm_flattened_mod = []
        if optimize_for == "Distance":
            for i in dm_flattened:
                i= int(i*1000)
                dm_flattened_mod.append(i)
            dm_flattened = dm_flattened_mod
        distance_matrix = list(unflatten_list(dm_flattened, num_locations))
        print("DistanceMatrix", distance_matrix)
        return distance_matrix
    #########################################################################################################################################
    ### Function to calculate haversine estimate ("as the crow flies") for values that fall outside bounds of route matrix. For more, see ###
    ### https://docs.aws.amazon.com/location/latest/developerguide/calculate-route-matrix.html#matrix-routing-position-limits             ###
    #########################################################################################################################################
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
        print("V2Dmatrix")
        print(dmatrix)
        return dmatrix * 1000
    
    def label_nodes(i):
        shortest_route = []
        for x in i:
            shortest_route.append(place_names[x])
            shortest_route.append(points[x])
        shortest_route.append(place_names[0])
        shortest_route.append(points[0])
        print("Shortest Route:", shortest_route)
        return shortest_route

        # implementation of traveling Salesman Problem
    
    def get_solution2(manager, routing, solution, num_vehicles):
        """Gets solution for multiple vehicles."""
        # print(num_vehicles,"num_vehicles in get_solution2")
        
        print(f'Objective: {solution.ObjectiveValue()}')
        total_distance = 0
        
        all_vehicle_routes = {}
        
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            print("INDEX", index)
            print("----------------------")
            plan_output = 'Route for vehicle {}:'.format(vehicle_id)
            #print(plan_output)
            route_distance = 0
            all_vehicle_routes[vehicle_id]={'nodes':[index]}
            #plan_output = 'Starting point for vehicle {} is {},'.format(vehicle_id,index)
            #print(plan_output)
            while not routing.IsEnd(index):
                plan_output += ' {} ->'.format(manager.IndexToNode(index))
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                # route_distance += routing.GetArcCostForVehicle(
                #     previous_index, index, vehicle_id)
                all_vehicle_routes[vehicle_id]['nodes'].append(index)
                print("ALL_VEHICLE_ROUTES_PRE",all_vehicle_routes)
                route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            print("Route Distance", route_distance)
            all_vehicle_routes[vehicle_id]['route_distance']=(route_distance)
            #Hard coding to overwrite here, since for multiple vehicles, index seems to be continuious? 
            all_vehicle_routes[vehicle_id]['route_distance']=(route_distance)
            all_vehicle_routes[vehicle_id]['nodes'][0]=0
            all_vehicle_routes[vehicle_id]['nodes'][-1]=0
            print("ALL_VEHICLE_ROUTES_POST", all_vehicle_routes)
            plan_output += ' {}\n'.format(manager.IndexToNode(index))
            if optimize_for == "Distance":
                plan_output += 'Distance of the route: {} Miles\n'.format(route_distance)
            if optimize_for == "DurationSeconds":
                plan_output += 'Duration of the route: {} Seconds\n'.format(route_distance)
            #print(plan_output)
            total_distance += route_distance
            
            all_vehicle_routes[vehicle_id]['plan_output'] = plan_output
        
        all_vehicle_routes['total_distance'] = total_distance/1000
        
        print('All Vehicle Routes:', all_vehicle_routes)
        print('Total Distance of all routes: {}m'.format(total_distance))
        
        # print("!!! Returning all_vehicle_routes !!!",all_vehicle_routes)
    
        return all_vehicle_routes
    
    
    
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
        # print(plan_output)
        if optimize_for == "Distance":
            plan_output += 'Distance of the route: {} Mile(s)\n'.format(route_distance/1000)
        if optimize_for == "DurationSeconds":
            plan_output += 'Objective: {}Seconds\n'.format(route_distance)
        
        all_vehicle_routes={}
        all_vehicle_routes[0] = {'nodes':nodes,'plan_output':plan_output,'route_distance':route_distance}
        all_vehicle_routes['total_distance']=route_distance
        print('All Vehicle Routes', all_vehicle_routes)
        return all_vehicle_routes #nodes, plan_output,route_distance


    def solve(num_locations, graph, starting_node, num_vehicles=1):
        print(num_vehicles,"num_vehicles in solve")
        from ortools.constraint_solver import pywrapcp
        # Create the routing index manager.
        manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, starting_node) 
    
        # Create Routing Model.
        routing = pywrapcp.RoutingModel(manager)
    
        distance_matrix = graph
    
        def distance_callback(from_index, to_index):
            """Returns the distance between the two nodes."""
            # Convert from routing variable Index to distance matrix NodeIndex.
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]
            print("FROMNODETONODE")
            print(distance_matrix[from_node][to_node])
        # Create counter
        def counter_callback(from_index):
            """Returns 1 for any locations except depot."""
            # Convert from routing variable Index to user NodeIndex.
            from_node = manager.IndexToNode(from_index)
            return 1 if (from_node != 0) else 0;
    
        counter_callback_index = routing.RegisterUnaryTransitCallback(counter_callback)
        #routing.Add(solver.MakeLessOrEqual.counter_callback_index, )
        routing.AddDimensionWithVehicleCapacity(
            counter_callback_index,
            0,  # null slack
            [delivery_per_vehicle]*num_vehicles,  # maximum locations per vehicle
            True,  # start cumul to zero
            'Counter')
    
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    
        # Define cost of each arc.
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        print(routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index))
        
        # Add Distance constraint.
        dimension_name = 'Distance'
        max_travel_distance = 100000
        routing.AddDimensionWithVehicleCapacity
        routing.AddDimension(
            transit_callback_index,
            0,  # no slack
            max_travel_distance,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name)
        # distance_dimension = routing.GetDimensionOrDie(dimension_name)
        # distance_dimension.SetGlobalSpanCostCoefficient(1000)
        
        
        # Setting first solution heuristic.
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
        # Solve the problem.
        solution = routing.SolveWithParameters(search_parameters)
    
        # Print solution on console.
        if solution and num_vehicles==1:
            return get_solution(manager, routing, solution)
            
        elif solution and num_vehicles>1:
            # print(solution)
            # print(num_vehicles)
            # print("***")
            print(f'Objective: {solution.ObjectiveValue()}')
            return get_solution2(manager, routing, solution, num_vehicles) 
            
        else:
            return "no solution found"

        
    def solve_for_traveling_salesperson_v2(num_locations, graph, starting_node, num_vehicles):
        print("graph", graph)
        print("num locations", num_locations)
        print("starting node", starting_node)
        print("num vehicles", num_vehicles)
        try:
            all_vehicle_routes = solve(num_locations,graph, starting_node, num_vehicles)
            print("all_vehicle_routes=",all_vehicle_routes)
            voutput = {}
            for vid in range(num_vehicles):
                nodes = all_vehicle_routes[vid]['nodes']
                print("NODES")
                print(nodes)
                min_path = all_vehicle_routes[vid]['route_distance']
                
                print(f"Vehicle id:{vid} with {len(nodes)-1} nodes")
                print(min_path)
                voutput[vid] = (min_path), label_nodes(nodes[0:-1])
            
            print("returning voutput")
            print(voutput)
            return voutput
            print(min_path)
                
        except Exception as e:
            print("error in v2 solve")
            print(e)
        
    ### Execute funtions
    try:
        decode_list(coordinates)
        
    except:
        print('Something went wrong decoding coordinates')
    try:
        # distance_matrix = build_distance_matrix(points) # Esri - 10, Here - 350 limit for locations
        location_service_matrix = build_distance_matrix(points)
        print("Routes Calculated Using Distance Matrix From Amazon Location Service")
    
    except: 
        location_service_matrix = build_distance_matrix_v2(points)
        print("Routes Calculated Using Haversine Approximate Estimate for Distance Matrix")
    
    try: 
        # solution = solve_for_traveling_salesperson(distance_matrix, starting_node)
        solution = solve_for_traveling_salesperson_v2(num_locations,location_service_matrix, starting_node, num_vehicles)
        print("Solution:", solution)
    
        # solution is voutput
   
    
    except Exception as e:
        print(e)
        solution=(e,0)
        print('Could not find the Optimal Route')
    
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
