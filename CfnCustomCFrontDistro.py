import logging
import boto3
from botocore.exceptions import ClientError
from crhelper import CfnResource
import CFrontClasses
from str2bool import str2bool

logger = logging.getLogger(__name__)
# Initialise the helper, all inputs are optional, this example shows the defaults
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')

CFN_STATES = {
    "failed": ["CREATE_FAILED", "ROLLBACK_IN_PROGRESS", "ROLLBACK_FAILED", "ROLLBACK_COMPLETE", "DELETE_FAILED",
               "UPDATE_ROLLBACK_IN_PROGRESS", "UPDATE_ROLLBACK_FAILED", "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
               "UPDATE_ROLLBACK_COMPLETE"],
    "in_progress": ["CREATE_IN_PROGRESS", "DELETE_IN_PROGRESS", "UPDATE_IN_PROGRESS",
                    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "InProgress"],
    "success": ["CREATE_COMPLETE", "DELETE_COMPLETE", "UPDATE_COMPLETE", "Deployed"]
}

EXPECTED_CREATE_RESPONSE_KEYS = [{"Distribution": ["Id", "ARN", "Status", "DomainName", "DistributionConfig"]}]


# TODO: don't forget to make attribs for Fn::GetAtt that covers 'DomainName' of resource (the cfront distro domain name)

try:
    cfclient = boto3.client('cloudfront')
except Exception as e:
    helper.init_failure(e)

# create cfront distro with origin group
#{
#   "RequestType" : "Create",
#   "ResponseURL" : "http://pre-signed-S3-url-for-response",
#   "StackId" : "arn:aws:cloudformation:us-west-2:123456789012:stack/stack-name/guid",
#   "RequestId" : "unique id for this create request",
#   "ResourceType" : "Custom::TestResource",
#   "LogicalResourceId" : "MyTestResource",
#   "ResourceProperties" : {
#      "DistroConfig" : "Value"
#   }
#}

@helper.create
def create(event, context):
    logger.info(f"Create event received:"
                f"{event}")
    # Optionally return an ID that will be used for the resource PhysicalResourceId,
    # if None is returned an ID will be generated. If a poll_create function is defined
    # return value is placed into the poll event as event['CrHelperData']['PhysicalResourceId']
    #
    # To add response data update the helper.Data dict
    # If poll is enabled data is placed into poll event as event['CrHelperData']

    try:
        if "Tags" in event["ResourceProperties"]:
            target_create_distro = CFrontClasses.Distribution.from_cfn_form(
                distributionConfigDict=event["ResourceProperties"]["DistributionConfig"],
                tagsList=event["ResourceProperties"]["Tags"])
            logger.info(f"create payload:"
                        f"{target_create_distro.to_dict()}")
            response = cfclient.create_distribution_with_tags(
                DistributionConfigWithTags=target_create_distro.to_dict())
        else:
            target_create_distro = CFrontClasses.Distribution.from_cfn_form(
                event["ResourceProperties"]["DistributionConfig"])
            logger.info(f"create payload:"
                        f"{target_create_distro.to_dict()}")
            response = cfclient.create_distribution(
                DistributionConfig=target_create_distro.DistributionConfig.to_dict())  # we need ONLY the distro config here, not a dict with keys for it and tags like prior

    except Exception as createDistroConfigEx:
        raise createDistroConfigEx

    try:
        validresponse = validate_response_dict(response, EXPECTED_CREATE_RESPONSE_KEYS)
    except Exception as validateEx:
        logger.error(f"response validation error:\n {str(validateEx)}")
        raise validateEx

    logger.info(f"resource CREATE:"
               f" ID: {response['Distribution']['Id']}"
               f" ARN: {response['Distribution']['ARN']}"
               f" DomainName: {response['Distribution']['DomainName']}"
               f" Status: {response['Distribution']['Status']}")

    helper.Data.update({"ARN": response["Distribution"]["ARN"]})
    helper.Data.update({"DomainName": response["Distribution"]["DomainName"]})
    helper.PhysicalResourceId = response["Distribution"]["Id"]
    return response["Distribution"]["Id"]


@helper.update
def update(event, context):
    logger.info(f"Update event received:"
                f"{event}")

    if "PhysicalResourceId" not in event.keys():
        raise ValueError(f"missing key 'PhysicalResourceId' in event data."
                         f"got: {event}")

    if "ResourceProperties" not in event.keys():
        raise ValueError(f"missing key 'ResourceProperties' (updated resource values) in event data."
                         f"got: {event}")

    if "OldResourceProperties" not in event.keys():
        raise ValueError(f"missing key 'OldResourceProperties' (original resource values) in event data."
                         f"got: {event}")

    if "Tags" in event["OldResourceProperties"].keys() or "Tags" in event["ResourceProperties"].keys() :
        fetchTags = True
    else:
        fetchTags = False

    # we need the ARN off the existing resource to be able to fetch tags by ARN of existing distribution
    #unsafe, see what happens if its deleted elsewhere by admin - 'i don't exist' - but told to update. should create?
    existingItemResponse = cfclient.get_distribution(Id=event["PhysicalResourceId"])

    logger.debug(f"existing live item response:"
                 f"{existingItemResponse}")

    existingItemTags = CFrontClasses.Tags(Items=[])  # instantiate for when fetchTags in untrue and later call to get_tag_update_work
    cfnTargetItemTags = None
    cfnOldItemTags = None  # we need old version tags in case they removed tags - we need to know which ones to remove that were there prior

    if fetchTags:
        existingItemTags = cfclient.list_tags_for_resource(Resource=existingItemResponse["Distribution"]["ARN"])
        if "Items" in existingItemTags["Tags"].keys():
            existingItemTags = CFrontClasses.Tags(Items=existingItemTags["Tags"]["Items"])
        else:
            existingItemTags = CFrontClasses.Tags(Items=[])

    if "Tags" in event["ResourceProperties"].keys():
        cfnTargetDistro = CFrontClasses.Distribution.from_cfn_form(distributionConfigDict=event["ResourceProperties"]["DistributionConfig"],
                                                                   tagsList=event["ResourceProperties"]["Tags"])
        targetItemTags = CFrontClasses.Tags.from_cfn_form(tagList=event["ResourceProperties"]["Tags"])
    else:
        cfnTargetDistro = CFrontClasses.Distribution.from_cfn_form(distributionConfigDict=event["ResourceProperties"]["DistributionConfig"])

    # we set the caller resource id once upon a time in a create event. we'll need that for equality compares - its not in the cfn data
    cfnTargetDistro.DistributionConfig.CallerReference = existingItemResponse["Distribution"]["DistributionConfig"]["CallerReference"]

    if "Tags" in event["OldResourceProperties"].keys():
        cfnOldVersionDistro = CFrontClasses.Distribution.from_cfn_form(distributionConfigDict=event["OldResourceProperties"]["DistributionConfig"],
                                                                       tagsList=event["OldResourceProperties"]["Tags"])
        cfnOldItemTags = CFrontClasses.Tags.from_cfn_form(tagList=event["OldResourceProperties"]["Tags"])
    else:
        cfnOldVersionDistro = CFrontClasses.Distribution.from_cfn_form(distributionConfigDict=event["OldResourceProperties"]["DistributionConfig"])
    # we set the caller resource id once upon a time in a create event. we'll need that for equality compares - its not in the cfn data
    cfnOldVersionDistro.DistributionConfig.CallerReference = existingItemResponse["Distribution"]["DistributionConfig"]["CallerReference"]

    if cfnTargetDistro == cfnOldVersionDistro:
        logger.info(f"normally blow up here. target and original equal from cfn data.")

    # for tag matching, if we're not set as desired we need to prune the specific keys we care for, rather than untag the whole lot and set them again
    # as not doing so could remove tags from other things...

    if cfnTargetDistro.DistributionConfig.to_dict() != existingItemResponse["Distribution"]["DistributionConfig"]:
        logger.debug(f"INEQUALITY detected between target cfn distribution config and existing live item distro config:"
                    f"** target from cfn: **"
                    f"{cfnTargetDistro.DistributionConfig.to_dict()}"
                    f"** existing live item distro config: **"
                    f"{existingItemResponse['Distribution']['DistributionConfig']}")
    else:
        logger.debug(f"EQUALITY detected between target cfn distribution config and existing live item distro config:"
                    f"** target from cfn: **"
                    f"{cfnTargetDistro.DistributionConfig.to_dict()}"
                    f"** existing live item distro config: **"
                    f"{existingItemResponse['Distribution']['DistributionConfig']}")

    tagWork = get_tag_update_work(existingLiveItemTags=existingItemTags,
                                  cfnTargetItemTags=cfnTargetItemTags,
                                  cfnOldItemTags=cfnOldItemTags)

    if len(tagWork["Tags"]) > 0:
        logger.info(f"adding new tags to existing resource:"
                    f"{tagWork['Tags']}")
        tagResponse = cfclient.tag_resource(Resource=existingItemResponse["Distribution"]["ARN"],
                                            Tags={"Items": tagWork["Tags"]})

    if len(tagWork["UntagKeys"]) > 0:
        logger.info(f"removing tags from existing resource:"
                    f"{tagWork['UntagKeys']}")
        untagResponse = cfclient.untag_resource(Resource=existingItemResponse["Distribution"]["ARN"],
                                                TagKeys={"Items": tagWork["UntagKeys"]})

    if not "ETag" in existingItemResponse.keys():
        raise ValueError(f"got no etag for existing live resource. cannot process update.")

    try:
        updateResponse = cfclient.update_distribution(
            DistributionConfig=cfnTargetDistro.DistributionConfig.to_dict(),
            Id=existingItemResponse["Distribution"]["Id"],
            IfMatch=existingItemResponse["ETag"]
        )
    except ClientError as updateError:
        if "No updates are to be performed" not in str(updateError):
            raise updateError

    helper.Data.update({"ARN": existingItemResponse["Distribution"]["ARN"]})
    helper.Data.update({"DomainName": existingItemResponse["Distribution"]["DomainName"]})

    return existingItemResponse["Distribution"]["Id"]


@helper.delete
def delete(event, context):
    logger.info("Got Delete")

    try:
        existingItemResponse = cfclient.get_distribution(Id=event["PhysicalResourceId"])
    except ClientError as getDistroError:
        if "The specified distribution does not exist" in str(getDistroError):
            return  # delete should not fail if the resource to be deleted no longer exists
        raise getDistroError

    if "ETag" not in existingItemResponse.keys():
        raise ValueError(f"got no etag from existing live item. cannot process disablement>delete"
                         f"{existingItemResponse}")

    existingItemDistroConfig = existingItemResponse["Distribution"]["DistributionConfig"]


    try:
        if isinstance(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"], bool):
            existingIsEnabled = existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"]
        elif isinstance(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"], str):
            existingIsEnabled = str2bool(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"],
                                         raise_exc=True)
    except Exception as castEx:
        logger.error(f"unable to cast existing live item distro config 'Enabled' state to bool. got:"
                     f" {existingItemResponse}")

    if existingItemResponse["Distribution"]["Status"] in CFN_STATES['in_progress']:
        return None

    if existingIsEnabled and existingItemResponse["Distribution"]["Status"] in CFN_STATES['success']:
        # need to disable the distro prior to delete
        try:
            existingItemDistroConfig["Enabled"] = False
            updateResponse = cfclient.update_distribution(
                DistributionConfig=existingItemDistroConfig,
                Id=existingItemResponse["Distribution"]["Id"],
                IfMatch=existingItemResponse["ETag"]
            )
        except ClientError as updateError:
            if "No updates are to be performed" not in str(updateError):
                raise updateError
        return None

    if not existingIsEnabled and existingItemResponse["Distribution"]["Status"] in CFN_STATES['success']:
        try:
            deleteResponse = cfclient.delete_distribution(
                Id=existingItemResponse["Distribution"]["Id"],
                IfMatch=existingItemResponse["ETag"])
        except ClientError as deleteError:
            logger.error(f"error on delete of cfront distro:"
                         f" ID: {existingItemResponse['Distribution']['Id']}"
                         f" exception: "
                         f" {str(deleteError)}")
            raise deleteError


@helper.poll_create
@helper.poll_update
def poll_create_update(event, context):
    logger.info(f"Got poll create/update event:"
                f"{event}")
    try:
        existingItemResponse = cfclient.get_distribution(Id=event["CrHelperData"]["PhysicalResourceId"])
    except ClientError as getDistroError:
        raise getDistroError

    helper.Data.update({"ARN": existingItemResponse["Distribution"]["ARN"]})
    helper.Data.update({"DomainName": existingItemResponse["Distribution"]["DomainName"]})

    if existingItemResponse["Distribution"]["Status"] in CFN_STATES['in_progress']:
        return None

    if existingItemResponse["Distribution"]["Status"] in CFN_STATES['success']:
        return event["CrHelperData"]["PhysicalResourceId"]

@helper.poll_delete
def poll_delete(event, context):
    logger.info(f"Got poll delete event:"
                f"{event}")
    try:
        existingItemResponse = cfclient.get_distribution(Id=event["PhysicalResourceId"])
    except ClientError as getDistroError:
        if "The specified distribution does not exist" in str(getDistroError):
            return event["PhysicalResourceId"]  # we're done, it's gone
        raise getDistroError

    try:
        if isinstance(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"], bool):
            existingIsEnabled = existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"]
        elif isinstance(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"], str):
            existingIsEnabled = str2bool(existingItemResponse["Distribution"]["DistributionConfig"]["Enabled"],
                                         raise_exc=True)
    except Exception as castEx:
        logger.error(f"unable to cast existing live item distro config 'Enabled' state to bool. got:"
                     f" {existingItemResponse}")

    # if we're doing something, wait / leave
    if existingItemResponse["Distribution"]["Status"] in CFN_STATES['in_progress']:
        return None

    existingItemDistroConfig = existingItemResponse["Distribution"]["DistributionConfig"]

    # we entered polling with the thing not disabled
    if existingIsEnabled and existingItemResponse["Distribution"]["Status"] in CFN_STATES['success']:
        # need to disable the distro prior to delete
        try:
            existingItemDistroConfig["Enabled"] = False
            updateResponse = cfclient.update_distribution(
                DistributionConfig=existingItemDistroConfig,
                Id=existingItemResponse["Distribution"]["Id"],
                IfMatch=existingItemResponse["ETag"]
            )
        except ClientError as updateError:
            if "No updates are to be performed" not in str(updateError):
                raise updateError
        return None

    if not existingIsEnabled and existingItemResponse["Distribution"]["Status"] in CFN_STATES['success']:
        # ready to be deleted
        try:
            deleteResponse = cfclient.delete_distribution(
                Id=existingItemResponse["Distribution"]["Id"],
                IfMatch=existingItemResponse["ETag"])
        except ClientError as deleteError:
            logger.error(f"error on delete of cfront distro:"
                         f" ID: {existingItemResponse['Distribution']['Id']}"
                         f" exception: "
                         f" {str(deleteError)}")
            raise deleteError

def lambda_handler(event, context):
    helper(event, context)

def get_tag_update_work(existingLiveItemTags: CFrontClasses.Tags,
                        cfnTargetItemTags: CFrontClasses.Tags,
                        cfnOldItemTags: CFrontClasses.Tags) -> dict:

    # this should never be None.  we either got a list of tags from the resource in caller, or instantiated an empty CFrontClasses.Tags
    if not isinstance(existingLiveItemTags, CFrontClasses.Tags):
        raise TypeError(f"expected CFrontClasses.Tags object for existing live item tags. got: {type(existingLiveItemTags)}")

    retval = {}
    retval["UntagKeys"] = []
    retval["Tags"] = []

    existingLiveItemNestedTagKeys = []
    for dictitem in existingLiveItemTags.Items:
        existingLiveItemNestedTagKeys.append(dictitem["Key"])

    # target may be NoneType - the whole cfn tags block was removed
    # ^ if this is the case then old config should also be None, or specify tags which were there prior
    if cfnTargetItemTags is None or cfnTargetItemTags.Items is None or len(cfnTargetItemTags.Items) == 0:
        if cfnOldItemTags is not None and cfnOldItemTags.Items is not None and len(cfnOldItemTags.Items) > 0:
            if len(existingLiveItemTags.Items) > 0:
                for untagItem in cfnOldItemTags.Items:
                    if untagItem.Key in existingLiveItemNestedTagKeys:
                        retval["UntagKeys"].append(untagItem.Key)

    if cfnTargetItemTags is not None and cfnTargetItemTags.Items is not None and len(cfnTargetItemTags.Items) > 0:
        for tagDict in cfnTargetItemTags.Items:
            if tagDict.Key in existingLiveItemNestedTagKeys:
                for i in range(len(existingLiveItemTags.Items)):
                    if tagDict.Key == existingLiveItemTags.Items[i].Key:
                        if tagDict.Value != existingLiveItemTags.Items[i].Value:
                            retval["Tags"].append(tagDict.to_dict())
            else:
                retval["Tags"].append(tagDict.to_dict())

    # if existing live items tags has tags which did not come from cfn, we leave these alone

    return retval

def validate_response_dict(response: dict, validateKeyList: list) -> bool:
    if not isinstance(response, dict):
        raise TypeError(f"'response' must be of type dict. got: {type(response)}")
    if not isinstance(validateKeyList, list):
        raise TypeError(f"'validateKeyList' must be of type list. got: {type(validateKeyList)}")

    for validateItem in validateKeyList:
        if isinstance(validateItem, dict):
            for itemkey in validateItem.keys():
                if itemkey not in response.keys():
                    raise ValueError(f"did not get '{itemkey}' key in response dict."
                                     f"got: {response}")
                if isinstance(validateItem[itemkey], str):
                    if validateItem[itemkey] not in response[itemkey].keys():
                        raise ValueError(f"did not get '{validateItem[itemkey]}' key in response['{itemkey}']."
                                         f"got: {response}")
                elif isinstance(validateItem[itemkey], list):
                    for listitem in validateItem[itemkey]:
                        if listitem not in validateItem[itemkey]:
                            raise ValueError(f"did not get '{listitem}' key in response['{itemkey}']."
                                             f"got: {response}")
        elif isinstance(validateItem, str):
            if validateItem not in response.keys():
                raise ValueError(f"did not get '{validateItem}' key in response."
                                 f"got: {response}")
        else:
            raise TypeError(f"expected 'str' or 'dict' to validate. got: {type(validateItem)}")
    return True
