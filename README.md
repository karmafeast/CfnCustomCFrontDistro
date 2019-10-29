# Custom::CFrontDistro

## USE

Use this custom resource as if a regular AWS::CloudFront::Distribution, with additional syntax available for the configuration and use of origin groups (see below section)

Native AWS::CloudFront::Distribution documentation implies (correctly in this case) that an origin group can be used in cache behaviors / default cache behavior as the target origin.

While this is true in this custom resource, there is no ability to create an origin group in the native resource (10/2019).
Regardless of the documentation state at AWS - you can do as it says with this resource.

## Method of Operation

A cloudformation custom resource for CloudFront distributions is lifecycle managed by an associated lambda function in this instance.

This function must exist for the custom resource to be able to be created, and its ARN must be referenced in the custom resource declaration in its 'ServiceToken' property

```JSON
{
...
    {"MyDistro":
      "Type": "Custom::CFrontDistro",
      {"Properties":
        {
          "ServiceToken":"ARN_TO_FUNCTION",
          "DistributionConfig": {"keys": "values"}
        }
      }
    }
}
```

## New things in the distribution config

You may specify origin groups in a form that should appear familiar to those using cloudformation.


### OriginGroups list (of dict items) --
A complex type that contains information about origin groups for this distribution.

### OriginGroups list item(dict) --
An origin group includes two origins (a primary origin and a second origin to failover to) and a failover criteria that you specify. 

NOTE - the FIRST ITEM in the list of 'Members' will be the primary origin of the pair.

You create an origin group to support origin failover in CloudFront. 

When you create or update a distribution, you can specify the origin group instead of a single origin, and CloudFront will failover 
from the primary origin to the second origin under the failover conditions that you've chosen.

### Id (string) -- [REQUIRED]
The origin group's ID.  This is a string, and one that should match cache behavior entries where this origin group is referenced

### FailoverCriteria (dict) -- [REQUIRED]
A complex type that contains information about the failover criteria for an origin group.

### StatusCodes (list) -- [REQUIRED]
The status codes that, when returned from the primary origin, will trigger CloudFront to failover to the second origin.
The StatusCodes list is the FailoverCriteria dict (see examples).  
these are integer numbers for the 400/500 HTTPStatus codes that invoke failover in the origin group.

### Members (list) -- [REQUIRED]
A complex type that contains information about the origins in an origin group.

NOTE - the FIRST ITEM in the list of 'Members' will be the primary origin of the pair.

NOTE - the 'ID' of the member origin group should be used.  These should be specified elsewhere in the distribution config as normal.

~~~YAML
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Custom Resource for CloudFront Distribution, supporting origin groups
Resources:
  CustomCFrontDistro:
    Type: Custom::CFrontDistro
    Properties:
      ServiceToken:
        Fn::ImportValue: CustomCFrontDistributionFunctionARN
      DistributionConfig:
#...
        OriginGroups:
          - Id: testyorigingroup
            FailoverCriteria:
              StatusCodes:
              - 403
              - 404
              - 500
              - 502
              - 503
              - 504
            Members:
              - my_fake_origin_1
              - my_fake_origin_2
            CustomErrorResponses:
            - ErrorCode: 403
              ResponsePagePath: "/some/path/to/here"
              ResponseCode: 200
              ErrorCachingMinTTL: 999
#... rest of distribution config
~~~

~~~JSON
{
   "OriginGroups":[
      {
         "Id":"testyorigingroup",
         "FailoverCriteria":{
            "StatusCodes":[
               403,
               404,
               500,
               502,
               503,
               504
            ]
         },
         "Members":[
            "my_fake_origin_1",
            "my_fake_origin_2"
         ]
      }
   ],
   "CustomErrorResponses":[
      {
         "ErrorCode":403,
         "ResponsePagePath":"/some/path/to/here",
         "ResponseCode":200,
         "ErrorCachingMinTTL":999
      }
   ]
}
~~~

## How to Deploy the Custom Resource Lambda

Your ```Custom::CFrontDistro``` containing template must have a 'ServiceToken' property, which is the ARN to the lambda function which manages
the custom resource lifecycle.

There are two ways you could achieve this.

### 1. deploy the function as a separate stack, export its ARN in the template. Import that exported ARN value into template where resource is used.

This method is preferred if you wish to have a single cloudwatch log stream to examine for the resource lambda actions in a given account, rather than
the second method, which will deploy a lambda function independently in each template where it is used.

You will get better debug using this method - as if there is failure in a template where the function itself is a resource, it will be purged along with
the rest of the stack if creation fails.

### 2. deploy the function and the resource together in a single template - elect not to reuse the resource lambda

More portable in some regards, in that you don't end up referencing a cfn export to locate the ARN of the custom resource function

Fragmented logging, overdeployment of lambda functions (per template vs shared per account).

Tighter permission control is possible if you deploy with the resource to manage a sinlge distro, in that you can restrict things like s3 bucket acl get/put to target distro
access logging bucket.

### Notes on IAM Permissions for Custom Resource Function

Shown in Examples section below.

Remember, the resource creations are occurring with the lambda execution context - NOT whatever is running the CloudFormation template.

To this end, the lambda execution will require full ability to manage CloudFront resources.

Similarly it will require access to CloudWatch to configure events for its own execution, and for options that might be specified in a resource.

The role will also require ability to list all s3 buckets, and to get/set acls on buckets - to support configuration of resources that elect to include
logging.

To support polling for long operations in cloudformation associated with cloudfront distros (a create or update can take many minutes to return),
the lambda function does not attempt to wait for readieness of a managed resource before returning.

Instead it sets up polling of itself and the lambda function handler routes events based on their type from cloudformation (e.g. poll_update).
There is a return format which allows cloudformation to poll for a resource's change to desired state 'SUCCESS' following a configuration change.

## Examples

### Lambda Function for Custom Resource

~~~YAML
---
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Custom Resource for CloudFront Distribution, supporting origin groups
Resources:
  CustomCFrontDistributionFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: customCFrontDistro/
      Handler: customCFrontDistro.lambda_handler
      Runtime: python3.7
      Role:
        Fn::GetAtt:
        - IARCustomCFrontDistribution
        - Arn
      Timeout: 300
  IARCustomCFrontDistribution:
    Type: AWS::IAM::Role
    Properties:
      ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      - arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess
      - arn:aws:iam::aws:policy/CloudFrontFullAccess
      - arn:aws:iam::aws:policy/CloudWatchEventsFullAccess
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
        - Action:
          - sts:AssumeRole
          Effect: Allow
          Principal:
            Service:
            - lambda.amazonaws.com
  IAMPS3Policy:
    Type: AWS::IAM::ManagedPolicy
    Properties:
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
        - Effect: Allow
          Action:
          - s3:ListAllMyBuckets
          - s3:GetBucketAcl
          - s3:PutBucketAcl
          Resource: "*"
      Roles:
      - Ref: IARCustomCFrontDistribution
  IAMPLambdaPerms:
    Type: AWS::IAM::ManagedPolicy
    Properties:
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
        - Effect: Allow
          Action:
          - lambda:AddPermission
          - lambda:RemovePermission
          - events:PutRule
          - events:DeleteRule
          - events:PutTargets
          - events:RemoveTargets
          Resource:
            Fn::GetAtt:
            - CustomCFrontDistributionFunction
            - Arn
      Roles:
      - Ref: IARCustomCFrontDistribution
Outputs:
  CustomCFrontDistributionFunctionARN:
    Description: Custom CFront Distribution Lambda Function ARN
    Value:
      Fn::GetAtt:
      - CustomCFrontDistributionFunction
      - Arn
    Export:
      Name: CustomCFrontDistributionFunctionARN

~~~

~~~JSON
{
   "AWSTemplateFormatVersion":"2010-09-09",
   "Transform":"AWS::Serverless-2016-10-31",
   "Description":"Custom Resource for CloudFront Distribution, supporting origin groups",
   "Resources":{
      "CustomCFrontDistributionFunction":{
         "Type":"AWS::Serverless::Function",
         "Properties":{
            "CodeUri":"customCFrontDistro/",
            "Handler":"customCFrontDistro.lambda_handler",
            "Runtime":"python3.7",
            "Role":{
               "Fn::GetAtt":[
                  "IARCustomCFrontDistribution",
                  "Arn"
               ]
            },
            "Timeout":300
         }
      },
      "IARCustomCFrontDistribution":{
         "Type":"AWS::IAM::Role",
         "Properties":{
            "ManagedPolicyArns":[
               "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
               "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess",
               "arn:aws:iam::aws:policy/CloudFrontFullAccess",
               "arn:aws:iam::aws:policy/CloudWatchEventsFullAccess"
            ],
            "AssumeRolePolicyDocument":{
               "Version":"2012-10-17",
               "Statement":[
                  {
                     "Action":[
                        "sts:AssumeRole"
                     ],
                     "Effect":"Allow",
                     "Principal":{
                        "Service":[
                           "lambda.amazonaws.com"
                        ]
                     }
                  }
               ]
            }
         }
      },
      "IAMPS3Policy":{
         "Type":"AWS::IAM::ManagedPolicy",
         "Properties":{
            "PolicyDocument":{
               "Version":"2012-10-17",
               "Statement":[
                  {
                     "Effect":"Allow",
                     "Action":[
                        "s3:ListAllMyBuckets",
                        "s3:GetBucketAcl",
                        "s3:PutBucketAcl"
                     ],
                     "Resource":"*"
                  }
               ]
            },
            "Roles":[
               {
                  "Ref":"IARCustomCFrontDistribution"
               }
            ]
         }
      },
      "IAMPLambdaPerms":{
         "Type":"AWS::IAM::ManagedPolicy",
         "Properties":{
            "PolicyDocument":{
               "Version":"2012-10-17",
               "Statement":[
                  {
                     "Effect":"Allow",
                     "Action":[
                        "lambda:AddPermission",
                        "lambda:RemovePermission",
                        "events:PutRule",
                        "events:DeleteRule",
                        "events:PutTargets",
                        "events:RemoveTargets"
                     ],
                     "Resource":{
                        "Fn::GetAtt":[
                           "CustomCFrontDistributionFunction",
                           "Arn"
                        ]
                     }
                  }
               ]
            },
            "Roles":[
               {
                  "Ref":"IARCustomCFrontDistribution"
               }
            ]
         }
      }
   },
   "Outputs":{
      "CustomCFrontDistributionFunctionARN":{
         "Description":"Custom CFront Distribution Lambda Function ARN",
         "Value":{
            "Fn::GetAtt":[
               "CustomCFrontDistributionFunction",
               "Arn"
            ]
         },
         "Export":{
            "Name":"CustomCFrontDistributionFunctionARN"
         }
      }
   }
}
~~~


### Resource use example

~~~YAML
---
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Custom Resource for CloudFront Distribution, supporting origin groups
Resources:
  CustomCFrontDistro:
    Type: Custom::CFrontDistro
    Properties:
      ServiceToken:
        Fn::ImportValue: CustomCFrontDistributionFunctionARN
      DistributionConfig:
        Comment: i am not real, only testy!
        Logging:
          Bucket: fake_name_thing.s3.amazonaws.com
        Enabled: true
        Restrictions:
          GeoRestriction:
            RestrictionType: none
            Quantity: 0
        ViewerCertificate:
          CloudFrontDefaultCertificate: true
        CacheBehaviors:
        - AllowedMethods:
          - GET
          - HEAD
          CachedMethods:
          - GET
          - HEAD
          Compress: false
          ForwardedValues:
            QueryString: false
          PathPattern: "*.hugwolf"
          TargetOriginId: testyorigingroup
          ViewerProtocolPolicy: https-only
        - Compress: false
          DefaultTTL: 600
          ForwardedValues:
            QueryString: false
          PathPattern: "*.fake_name_thing"
          TargetOriginId: testyorigingroup
          ViewerProtocolPolicy: https-only
        DefaultCacheBehavior:
          TargetOriginId: my_fake_origin_1
          ViewerProtocolPolicy: https-only
          ForwardedValues:
            QueryString: false
        HttpVersion: http2
        Origins:
        - Id: my_fake_origin_1
          DomainName: my_fake_origin_1.s3.amazonaws.com
          S3OriginConfig:
            OriginAccessIdentity: origin-access-identity/cloudfront/E_FAKE_ORIGIN_ACCESS_ID_1
        - Id: my_fake_origin_2
          DomainName: my_fake_origin_2.s3.amazonaws.com
          S3OriginConfig:
            OriginAccessIdentity: origin-access-identity/cloudfront/E_FAKE_ORIGIN_ACCESS_ID_2
        OriginGroups:
        - Id: testyorigingroup
          FailoverCriteria:
            StatusCodes:
            - 403
            - 404
            - 500
            - 502
            - 503
            - 504
          Members:
          - my_fake_origin_1
          - my_fake_origin_2
        CustomErrorResponses:
        - ErrorCode: 403
          ResponsePagePath: "/some/path/to/here"
          ResponseCode: 200
          ErrorCachingMinTTL: 999
Outputs:
  customCFrontDistroDomainName:
    Description: cloudfront distribution domain name
    Value:
      Fn::GetAtt:
      - CustomCFrontDistro
      - DomainName
  customCFrontDistroARN:
    Description: cloudfront distribution ARN
    Value:
      Fn::GetAtt:
      - CustomCFrontDistro
      - ARN

~~~

~~~JSON
   "Resources":{
      "CustomCFrontDistro":{
         "Type":"Custom::CFrontDistro",
         "Properties":{
            "ServiceToken": {"Fn::ImportValue": "CustomCFrontDistributionFunctionARN"},
            "DistributionConfig":{
               "Comment":"i am not real, only testy!",
               "Logging":{
                  "Bucket":"fake_name_thing.s3.amazonaws.com"
               },
               "Enabled":true,
               "Restrictions":{
                  "GeoRestriction":{
                     "RestrictionType":"none",
                     "Quantity":0
                  }
               },
               "ViewerCertificate":{
                  "CloudFrontDefaultCertificate":true
               },
               "CacheBehaviors":[
                  {
                     "AllowedMethods":[
                        "GET",
                        "HEAD"
                     ],
                     "CachedMethods":[
                        "GET",
                        "HEAD"
                     ],
                     "Compress":false,
                     "ForwardedValues":{
                        "QueryString":false
                     },
                     "PathPattern":"*.hugwolf",
                     "TargetOriginId":"testyorigingroup",
                     "ViewerProtocolPolicy":"https-only"
                  },
                  {
                     "Compress":false,
                     "DefaultTTL":600,
                     "ForwardedValues":{
                        "QueryString":false
                     },
                     "PathPattern":"*.fake_name_thing",
                     "TargetOriginId":"testyorigingroup",
                     "ViewerProtocolPolicy":"https-only"
                  }
               ],
               "DefaultCacheBehavior":{
                  "TargetOriginId":"my_fake_origin_1",
                  "ViewerProtocolPolicy":"https-only",
                  "ForwardedValues":{
                     "QueryString":false
                  }
               },
               "HttpVersion":"http2",
               "Origins":[
                  {
                     "Id":"my_fake_origin_1",
                     "DomainName":"my_fake_origin_1.s3.amazonaws.com",
                     "S3OriginConfig":{
                        "OriginAccessIdentity":"origin-access-identity/cloudfront/E_FAKE_ORIGIN_ACCESS_ID_1"
                     }
                  },
                  {
                     "Id":"my_fake_origin_2",
                     "DomainName":"my_fake_origin_2.s3.amazonaws.com",
                     "S3OriginConfig":{
                        "OriginAccessIdentity":"origin-access-identity/cloudfront/E_FAKE_ORIGIN_ACCESS_ID_2"
                     }
                  }
               ],
               "OriginGroups":[
                  {
                     "Id":"testyorigingroup",
                     "FailoverCriteria":{
                        "StatusCodes":[
                           403,
                           404,
                           500,
                           502,
                           503,
                           504
                        ]
                     },
                     "Members":[
                        "my_fake_origin_1",
                        "my_fake_origin_2"
                     ]
                  }
               ],
               "CustomErrorResponses":[
                  {
                     "ErrorCode":403,
                     "ResponsePagePath":"/some/path/to/here",
                     "ResponseCode":200,
                     "ErrorCachingMinTTL":999
                  }
               ]
            }
         }
      }
   },
   "Outputs": {
     "customCFrontDistroDomainName": {
       "Description": "cloudfront distribution domain name",
       "Value": {
         "Fn::GetAtt": [
           "CustomCFrontDistro",
           "DomainName"
         ]
       }
     },
     "customCFrontDistroARN": {
       "Description": "cloudfront distribution ARN",
       "Value": {
         "Fn::GetAtt": [
           "CustomCFrontDistro",
           "ARN"
         ]
       }
     }
   }
~~~

## ref
[cfn: AWS::CloudFront::Distribution](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudfront-distribution.html "cfn: AWS::CloudFront::Distribution")

[boto3 docs for CFront](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution "this is cfn data is translated into and from")
