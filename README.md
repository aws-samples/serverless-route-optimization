# Serverless Route Optimization
This solution was created to help customers get started with an easy to deploy end-to-end route optimization solution. 

It was released and demoed OnAir live at Re:Mars 2022 on 6/22/22. Link to come.

## Architecture
<img width="796" alt="Screen Shot 2022-06-21 at 8 47 53 AM" src="https://user-images.githubusercontent.com/73195085/174842637-b81f6a03-c699-475a-a7fa-eb34401237b8.png">


## Deploying the Project
### Prerequistes:

To use the SAM CLI, you need the following tools:
  - [AWS account](https://aws.amazon.com/free/?trk=ps_a134p000003yBfsAAE&trkCampaign=acq_paid_search_brand&sc_channel=ps&sc_campaign=acquisition_US&sc_publisher=google&sc_category=core&sc_country=US&sc_geo=NAMER&sc_outcome=acq&sc_detail=%2Baws%20%2Baccount&sc_content=Account_bmm&sc_segment=438195700994&sc_medium=ACQ-P%7CPS-GO%7CBrand%7CDesktop%7CSU%7CAWS%7CCore%7CUS%7CEN%7CText&s_kwcid=AL!4422!3!438195700994!b!!g!!%2Baws%20%2Baccount&ef_id=Cj0KCQjwsuP5BRCoARIsAPtX_wEmxImXtbdvL3n4ntAafj32KMc_sXL9Z-o8FyXVQzPk7w__h2FMje0aAhOFEALw_wcB:G:s&s_kwcid=AL!4422!3!438195700994!b!!g!!%2Baws%20%2Baccount&all-free-tier.sort-by=item.additionalFields.SortRank&all-free-tier.sort-order=asc&awsf.Free%20Tier%20Types=*all&awsf.Free%20Tier%20Categories=*all) 
  - AWS SAM CLI - [Install the SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
  - Python 3.9 or later - [download the latest of version of python](https://www.python.org/downloads/) 
  - An [AWS Identity and Access Managment](https://aws.amazon.com/iam/) role with appropriate access


### This Sample Includes: 
  - *template.yaml*: Contains the AWS SAM template that defines the application's AWS resources. Resources outlined in the template include Location Service Resources for Maps, Places, and Routes, Congito Authorizer, Lambda Function, API Gateway REST API, and Location Service Resources which includes a Place Index for Amazon Location Service
  - *route-optimizer-function/*: Contains the Lambda function logic that performs the optimization of routes. The function takes in a series of points, and returns the optimized route data.
  - *dependencies/*: Contains dependencies that are added as a Lambda layer upon deployment. Dependencies include Boto3 and OR-Tools.
  - *index_route_opt.html*: This file contains the front end code, written in HTML and JS. It uses Amplify Geo to create the map resource from Amazon Location Service, and MapLibre libraries to add layers. It can be deployed directly in a browser.
 
### Deploy the Sam-App:
1. Use `git clone https://github.com/aws-samples/serverless-route-optimization` to clone the repository to your environment where AWS SAM and python are installed.
2. Use ``cd ~/serverless-route-optimization``to change into the project directory containing the template.yaml file SAM uses to build your application. 
3. Use ``sam build`` to build your application using SAM. You should see:

![Screen Shot 2021-12-13 at 3 02 51 PM](https://user-images.githubusercontent.com/73195085/145883002-b2570833-c2ff-406a-9402-b23c2a366dd0.png)


4. Use `sam deploy --guided` to deploy the application to your AWS account. Enter custom values for the application parameters. 
    

<img width="1212" alt="Screen Shot 2022-06-21 at 7 58 17 PM" src="https://user-images.githubusercontent.com/73195085/174934245-1246c147-8fc1-4537-bfcd-558219b355fc.png">

5. Once your stack has deployed sucessfully, you will see 3 output parameters returned. For all 3 output parameters, replace the coresponding '<RESOURCE>' named inside the index_route_opt.html (approx lines 66-68, line 184). Also ensure to replace '<REGION>' with the coresponding region you deployed the stack in.

<img width="1280" alt="Screen Shot 2022-06-21 at 8 06 06 PM" src="https://user-images.githubusercontent.com/73195085/174935046-0e985c9b-f78c-4ad1-a960-eabb85fd3de5.png">

## Testing the Application

1. The index_route_opt.html is designed to work directly in your favorite browser without needing to host locally. Once you have edited the file to add the necessary outputs from the SAM deployment, you can drag and drop the file into your browser tab to begin testing!
2. Begin clicking points to optimize routes. Note by default, the optimized route will return to the origin, which is the first point selected.

<img width="1419" alt="Screen Shot 2022-06-21 at 7 43 30 PM" src="https://user-images.githubusercontent.com/73195085/174932289-f191fbb9-f4f1-4402-b5cb-272532b5b43a.png">





## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

