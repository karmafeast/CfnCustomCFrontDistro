# contains classes which represent a cloudfront distribution, and methods for their instantiation from CloudFormation style data
# cfn style data will be incoming to consumers of these classes when they are used as part of a cfn custom resource
#
# IN GENERAL - there is no strict validation of string content against matches, when this is possible
# while this could easily be added, it is omitted to allow this code to have a degree of future compatibility where
# new options are added.
# For example, there is no check on 'OriginSSLProtocols' to ensure they match expected values, if a new one was added
# you could use it if it were represented in the same fashion
#
# if invalid data is specified in a case such as the above, you'll end up being bounced by the api call itself, which
# will reject the form of your request due to inappropriate data values.
# code utilizing these classes should catch response errors, and respond appropriately, or in the simplest sense when
# acting as part of a cfn custom resource, simply allow the exception/error to raise out to terminate the lambda
#
# lambda function associations list entry dicts can contain key 'IncludeBody' - a bool
# logging configuration of a CFront distribution can be enabled/disabled

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from str2bool import str2bool
import uuid


def unix_epoch_ticks(dt):
    return (dt - datetime(1970, 1, 1)).total_seconds() * 10000000

def generate_caller_reference() -> str:
    return str(uuid.uuid4())


def trim_null_keys(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


dictfilt = lambda x, y: dict([(i, x[i]) for i in x if i in set(y)])


@dataclass
class StringListItems:
    Quantity: int
    Items: Optional[List[str]] = None

    @classmethod
    def from_cfn_form(cls, itemsList: List[str]) -> 'StringListItems':
        if not isinstance(itemsList, list):
            raise TypeError(f"expected list to convert to items/quantity form, got: {type(itemsList)}")

        if len(itemsList) == 0:
            return cls(Quantity=0)

        items = [str(i) for i in itemsList]
        return cls(Quantity=len(items), Items=items)

    def to_dict(self):
        if self.Items is None or len(self.Items) == 0:
            return {"Quantity": 0}  # omitting items on quantity 0
        return {"Quantity": len(self.Items), "Items": self.Items}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class OriginSslProtocols:
    Quantity: int
    Items: List[str]

    @classmethod
    def from_cfn_form(cls, originSslProtocolsList: List[str]) -> 'OriginSslProtocols':
        if not isinstance(originSslProtocolsList, list):
            raise TypeError(f"'OriginSslProtocols' is expected to be a list, got: {type(originSslProtocolsList)}")
        if len(originSslProtocolsList) == 0:
            raise ValueError("cannot instantiate zero item OriginSslProtocols")
        items = [str(i) for i in originSslProtocolsList]
        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        return {"Quantity": len(self.Items), "Items": self.Items}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()

# !N.B. 'CachedMethods' is a sub component of 'AllowedMethods' in api form, but are siblings in a cfn cache behavior!
@dataclass
class AllowedMethods:
    Quantity: int
    Items: List[str]
    CachedMethods: Optional[StringListItems] = None

    @classmethod
    def from_cfn_form(cls, allowedMethodsList: List[str] = None,
                      cachedMethodsList: List[str] = None) -> 'AllowedMethods':
        # cfn user may have ONLY specified cached methods, and accepted default for the allowed methods
        # in such a case we'll need to make allowed methods equal to cached methods
        #
        # we're not validating the strings they sent, other than for cached being a subset of allowed, and ensuring no duplicate values in a given list
        # if ONLY cached is specified, allowed will become cached
        if allowedMethodsList is None and cachedMethodsList is None:
            raise AssertionError("logic failure in AllowedMethods.from_cfn_form() - "
                                 "this constructor should not be called when allowedMethodsList and cachedMethodsList both None - "
                                 "instead, omit AllowedMethods from the relevant cache behavior api form")
        if allowedMethodsList is not None:
            if not isinstance(allowedMethodsList, list):
                raise TypeError(f"'AllowedMethods' must be a list (of strings). got: {type(allowedMethodsList)}")
            if len(allowedMethodsList) == 0:
                raise ValueError("'AllowedMethods' exists, but is empty list.")
            if len(set(allowedMethodsList)) != len(allowedMethodsList):
                raise ValueError(f"'AllowedMethods' contains duplicates. got: {allowedMethodsList}")
        if cachedMethodsList is not None:
            if not isinstance(cachedMethodsList, list):
                raise TypeError(f"'CachedMethods' must be a list (of strings). got: {type(cachedMethodsList)}")
            if len(cachedMethodsList) == 0:
                raise ValueError("'CachedMethods' exists, but is an empty list")
            if len(set(cachedMethodsList)) != len(cachedMethodsList):
                raise ValueError(f"'CachedMethods' contains duplicates. got: {cachedMethodsList}")

        # they've specified ONLY a cached methods list in the cfn form (which we make match here)
        #   - allowed methods should match cached methods
        if allowedMethodsList is None and cachedMethodsList is not None:
            allowedMethodsList = cachedMethodsList

        # while not documented, you can see the following in the aws gui for making a cfront distro.
        # cachedMethodsList must be a subset of allowed methods.
        # i.e. you CANNOT have cached with ["GET","HEAD","OPTIONS"] when allowed only has ["GET","HEAD"]
        if allowedMethodsList is not None and cachedMethodsList is not None:
            if not set(cachedMethodsList).issubset(set(allowedMethodsList)):
                raise ValueError(
                    f"'CachedMethods' must be a subset of 'AllowedMethods'. got AllowedMethods: {allowedMethodsList}, CachedMethods: {cachedMethodsList}")

        instantiate_args = {"Items": allowedMethodsList, "Quantity": len(allowedMethodsList)}

        if cachedMethodsList is not None:  # we've already validated is cached methods not None that its > 0 length list
            instantiate_args["CachedMethods"] = StringListItems.from_cfn_form(itemsList=cachedMethodsList)

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"Quantity": len(self.Items), "Items": self.Items}
        if self.CachedMethods is not None:
            retval["CachedMethods"] = self.CachedMethods.to_dict()
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Cookies:
    Forward: str  # if value is 'whitelist' there must be a list of 'WhiteListedNames'
    WhitelistedNames: Optional[StringListItems] = None

    @classmethod
    def from_cfn_form(cls, cookiesDict) -> 'Cookies':
        if not isinstance(cookiesDict, dict):
            raise TypeError(f"'Cookies' must be of type dict. got: {type(cookiesDict)}")
        if "Forward" not in cookiesDict.keys():
            raise ValueError(f"no 'Forward' in 'Cookies': {cookiesDict}")
        if not isinstance(cookiesDict["Forward"], str):
            raise TypeError(f"'Forward' in 'Cookies' must be a string. got: {type(cookiesDict['Forward'])}")

        instantiate_args = {"Forward": cookiesDict["Forward"]}

        if "WhitelistedNames" in cookiesDict.keys():
            if cookiesDict["Forward"] != 'whitelist':
                raise ValueError(
                    f"if 'WhitelistedNames' in 'Cookies', 'Forward' str must be 'whitelist'. got: {cookiesDict['Forward']}")
            if not isinstance(cookiesDict["WhitelistedNames"], list):
                raise TypeError(
                    f"'WhitelistedNames' in 'Cookies' must be a list (of strings). got: {type(cookiesDict['WhitelistedNames'])}")
            instantiate_args["WhitelistedNames"] = StringListItems.from_cfn_form(
                itemsList=cookiesDict["WhitelistedNames"])

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"Forward": self.Forward}
        if self.WhitelistedNames is not None:
            retval["WhitelistedNames"] = self.WhitelistedNames.to_dict()
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class ForwardedValues:
    QueryString: bool
    Cookies: Optional[Cookies] = None  # cfn: OPTIONAL, api: REQUIRED
    Headers: Optional[StringListItems] = None  # cfn: OPTIONAL, api: OPTIONAL
    QueryStringCacheKeys: Optional[StringListItems] = None  # cfn: OPTIONAL, api: OPTIONAL

    @classmethod
    def from_cfn_form(cls, forwardedValuesDict) -> 'ForwardedValues':
        if not isinstance(forwardedValuesDict, dict):
            raise TypeError(f"'ForwardedValues' must be a dict. got: {type(forwardedValuesDict)}")
        if "QueryString" not in forwardedValuesDict.keys():
            raise ValueError("no 'QueryString' in 'ForwardedValues'")

        instantiate_args = {}

        # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
        if isinstance(forwardedValuesDict["QueryString"], str):
            try:
                queryString_bool = str2bool(forwardedValuesDict["QueryString"], raise_exc=True)
            except Exception as CastEx:
                raise ValueError(
                    f"unable to cast string for 'ForwardedValues' 'QueryString' state to boolean. got: {forwardedValuesDict['QueryString']}"
                    f"{str(CastEx)}")
            instantiate_args["QueryString"] = queryString_bool
        elif isinstance(forwardedValuesDict["QueryString"], bool):
            instantiate_args["QueryString"] = forwardedValuesDict["QueryString"]
        else:
            raise TypeError(
                f"'QueryString' in 'ForwardedValues' must be of type str (cast) or bool. got {type(forwardedValuesDict['QueryString'])}")

        if "Cookies" in forwardedValuesDict.keys():
            if not isinstance(forwardedValuesDict["Cookies"], dict):
                raise TypeError(
                    f"'Cookies' in 'ForwardedValues' must be of type dict. got: {type(forwardedValuesDict['Cookies'])}")
            instantiate_args["Cookies"] = Cookies.from_cfn_form(forwardedValuesDict["Cookies"])
        else:
            instantiate_args["Cookies"] = Cookies(Forward="none")

        if "Headers" in forwardedValuesDict.keys():
            if not isinstance(forwardedValuesDict["Headers"], list):
                raise TypeError(
                    f"'Headers' in 'ForwardedValues' must be of type list (of strings). got: {type(forwardedValuesDict['Headers'])}")
            instantiate_args["Headers"] = StringListItems.from_cfn_form(itemsList=forwardedValuesDict["Headers"])
        else:
            instantiate_args["Headers"] = StringListItems(Quantity=0)
        if "QueryStringCacheKeys" in forwardedValuesDict.keys():
            if not isinstance(forwardedValuesDict["QueryStringCacheKeys"], list):
                raise TypeError(
                    f"'QueryStringCacheKeys' must be a list (of strings). got: {type(forwardedValuesDict['QueryStringCacheKeys'])}")
            instantiate_args["QueryStringCacheKeys"] = StringListItems.from_cfn_form(
                itemsList=forwardedValuesDict["QueryStringCacheKeys"])
        else:
            instantiate_args["QueryStringCacheKeys"] = StringListItems(Quantity=0)

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"QueryString": self.QueryString}
        if self.Cookies is not None:
            retval["Cookies"] = self.Cookies.to_dict()
        if self.Headers is not None:
            retval["Headers"] = self.Headers.to_dict()
        if self.QueryStringCacheKeys is not None:
            retval["QueryStringCacheKeys"] = self.QueryStringCacheKeys.to_dict()
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class LambdaFunctionAssociation:
    LambdaFunctionARN: str
    EventType: str
    IncludeBody: Optional[bool] = False

    @classmethod
    def from_cfn_form(cls, lambdaFunctAssocDict) -> 'LambdaFunctionAssociation':
        if not isinstance(lambdaFunctAssocDict, dict):
            raise TypeError(
                f"'LambdaFunctionAssociations' items must be of type dict. got: {type(lambdaFunctAssocDict)}")

        instantiate_args = {}

        if "LambdaFunctionARN" not in lambdaFunctAssocDict.keys():
            raise ValueError(
                f"'LambdaFunctionAssociations' items must contain dict key 'LambdaFunctionARN': {lambdaFunctAssocDict}")
        if not isinstance(lambdaFunctAssocDict["LambdaFunctionARN"], str):
            raise TypeError(
                f"'LambdaFunctionAssociations' items key 'LambdaFunctionARN' value must be of type string. got: {type(lambdaFunctAssocDict['LambdaFunctionARN'])}")
        instantiate_args["LambdaFunctionARN"] = lambdaFunctAssocDict["LambdaFunctionARN"]

        # viewer-request, origin-request, origin-response, viewer-response - not validating string as member of this list
        if "EventType" not in lambdaFunctAssocDict.keys():
            raise ValueError(
                f"'LambdaFunctionAssociations' items must contain dict key 'EventType': {lambdaFunctAssocDict}")
        if not isinstance(lambdaFunctAssocDict["EventType"], str):
            raise TypeError(
                f"'LambdaFunctionAssociations' items key 'EventType' value must be of type string. got: {type(lambdaFunctAssocDict['EventType'])}")
        instantiate_args["EventType"] = lambdaFunctAssocDict["EventType"]

        if "IncludeBody" in lambdaFunctAssocDict.keys():

            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(lambdaFunctAssocDict["IncludeBody"], str):
                try:
                    includeBody_bool = str2bool(lambdaFunctAssocDict["IncludeBody"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'LambdaFunctionAssociations' 'IncludeBody' state to boolean. got: {lambdaFunctAssocDict['IncludeBody']}"
                        f"{str(CastEx)}")
                instantiate_args["IncludeBody"] = includeBody_bool
            elif isinstance(lambdaFunctAssocDict["IncludeBody"], bool):
                instantiate_args["IncludeBody"] = lambdaFunctAssocDict["IncludeBody"]
            else:
                raise TypeError(
                    f"'IncludeBody' in 'LambdaFunctionAssociations' must be of type str (cast) or bool. got {type(lambdaFunctAssocDict['IncludeBody'])}")
        else:
            instantiate_args["IncludeBody"] = False

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"LambdaFunctionARN": self.LambdaFunctionARN, "EventType": self.EventType,
                  "IncludeBody": self.IncludeBody}
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class LambdaFunctionAssociations:
    Quantity: int
    Items: Optional[List[LambdaFunctionAssociation]] = None

    @classmethod
    def from_cfn_form(cls, lambdaFunctAssocList) -> 'LambdaFunctionAssociations':
        if not isinstance(lambdaFunctAssocList, list):
            raise TypeError(f"'LambdaFunctionAssociations' must be of type list. got: {type(lambdaFunctAssocList)}")
        if len(lambdaFunctAssocList) == 0:
            return cls(Quantity=0)

        items = []

        for assoc in lambdaFunctAssocList:
            items.append(LambdaFunctionAssociation.from_cfn_form(assoc))

        return cls(Quantity=len(items), Items=items)

    def to_dict(self):
        if self.Items is None:
            return {"Quantity": 0}
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()

# if not enabled, or no items MUST BE PRESENT for api
# cfn form does not seem to allow anything but a string list here, i.e. there's no bool for enabled
# "TrustedSigners": {
#    "Enabled": false,
#    "Quantity": 0
# }
@dataclass
class TrustedSigners:
    Enabled: bool
    Quantity: int
    Items: Optional[List[str]] = None

    # in cfn its coming at you as a list of strings - if the list is non-existent or not present, then self.Enabled set False
    @classmethod
    def from_cfn_form(cls, trustedSignersList) -> 'TrustedSigners':
        if not isinstance(trustedSignersList, list):
            raise TypeError(f"'TrustedSigners' must be a list (of strings). got: {type(trustedSignersList)}")
        instantiate_args = {}
        if len(trustedSignersList) == 0:
            instantiate_args["Enabled"] = False
            instantiate_args["Quantity"] = 0
            return cls(**instantiate_args)

        instantiate_args["Enabled"] = True
        instantiate_args["Items"] = trustedSignersList
        instantiate_args["Quantity"] = len(trustedSignersList)

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {}
        if self.Items is None or len(self.Items) == 0:
            retval["Enabled"] = False
            retval["Quantity"] = 0
        else:
            retval["Enabled"] = True
            retval["Quantity"] = len(self.Items)
            retval["Items"] = self.Items
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CacheBehavior:
    PathPattern: str
    TargetOriginId: str  # cfn: required, api: required
    ForwardedValues: ForwardedValues  # cfn: required, api: required
    ViewerProtocolPolicy: str  # cfn: required, api: required
    TrustedSigners: Optional[
        TrustedSigners] = None  # cfn: OPTIONAL (cfn docs inaccurate, appears to be list of what ends up in 'items'), api: required
    MinTTL: Optional[
        int] = 0  # cfn: OPTIONAL, # cfn: OPTIONAL, api: required - You must specify 0 for MinTTL if you configure CloudFront to forward all headers to your origin (under Headers , if you specify 1 for Quantity and * for Name). default: 0
    DefaultTTL: Optional[int] = 86400  # cfn: OPTIONAL, api: OPTIONAL. default 1d in seconds
    MaxTTL: Optional[int] = 31536000  # cfn: OPTIONAL, api: OPTIONAL. default 1y in seconds
    AllowedMethods: Optional[
        AllowedMethods] = None  # cfn: OPTIONAL, api: OPTIONAL - default appears to be ['GET','HEAD']
    SmoothStreaming: Optional[bool] = False  # cfn: OPTIONAL, api: OPTIONAL - default False
    Compress: Optional[bool] = False  # cfn: OPTIONAL, api: OPTIONAL. default False
    LambdaFunctionAssociations: Optional[LambdaFunctionAssociations] = None
    FieldLevelEncryptionId: Optional[str] = ""  # cfn: OPTIONAL, api: OPTIONAL on CREATE, req on update

    @classmethod
    def from_cfn_form(cls, cacheBehaviorDict) -> 'CacheBehavior':
        if not isinstance(cacheBehaviorDict, dict):
            raise TypeError(f"'CacheBehavior' must be of type dict, got: {type(cacheBehaviorDict)}")
        if "PathPattern" not in cacheBehaviorDict.keys():
            raise ValueError(f"'CacheBehavior' must contain key 'PathPattern'")
        if not isinstance(cacheBehaviorDict["PathPattern"], str):
            raise TypeError(
                f"'PathPattern' in a 'CacheBehavior' must be of type string. got: {type(cacheBehaviorDict['PathPattern'])}")
        if "*" == cacheBehaviorDict["PathPattern"]:
            raise ValueError(
                f"'PathPattern' in a 'CacheBehavior' cannot be '*' - this value reserved for 'DefaultCacheBehavior'")

        if "TargetOriginId" not in cacheBehaviorDict.keys():
            raise ValueError(f"no 'TargetOriginId' in 'CacheBehavior': {cacheBehaviorDict}")
        if not isinstance(cacheBehaviorDict["TargetOriginId"], str):
            raise TypeError(
                f"'TargetOriginId' in 'CacheBehavior' must be of type string. got: {type(cacheBehaviorDict['TargetOriginId'])}")
        if "ForwardedValues" not in cacheBehaviorDict.keys():
            raise ValueError(f"no 'ForwardedValues' in 'CacheBehavior': {cacheBehaviorDict}")
        if not isinstance(cacheBehaviorDict["ForwardedValues"], dict):
            raise TypeError(
                f"'ForwardedValues' in 'CacheBehavior' must be of type dict, got: {type(cacheBehaviorDict['ForwardedValues'])}")
        if "ViewerProtocolPolicy" not in cacheBehaviorDict.keys():
            raise ValueError(f"no 'ViewerProtocolPolicy' in 'CacheBehavior': {cacheBehaviorDict}")
        if not isinstance(cacheBehaviorDict["ViewerProtocolPolicy"], str):
            raise TypeError(
                f"'ViewerProtocolPolicy' in 'CacheBehavior' must be of type string. got: {type(cacheBehaviorDict['ViewerProtocolPolicy'])}")

        instantiate_args = {"PathPattern": cacheBehaviorDict["PathPattern"],
                            "TargetOriginId": cacheBehaviorDict["TargetOriginId"],
                            "ForwardedValues": ForwardedValues.from_cfn_form(cacheBehaviorDict["ForwardedValues"]),
                            "ViewerProtocolPolicy": cacheBehaviorDict["ViewerProtocolPolicy"]}
        # trusted signers is a list of strings from cfn, despite the cfn docs being super crazy on the subject and talking to the api form of this data element

        if "TrustedSigners" in cacheBehaviorDict.keys():
            if not isinstance(cacheBehaviorDict["TrustedSigners"], list):
                raise TypeError(
                    f"'TrustedSigners' in 'CacheBehavior' must be of type list. got: {type(cacheBehaviorDict['TrustedSigners'])}")
            instantiate_args["TrustedSigners"] = TrustedSigners.from_cfn_form(cacheBehaviorDict["TrustedSigners"])
        else:
            instantiate_args["TrustedSigners"] = TrustedSigners(Enabled=False, Quantity=0)

        if "MinTTL" in cacheBehaviorDict.keys():
            if isinstance(cacheBehaviorDict["MinTTL"], str):
                cacheBehaviorDict["MinTTL"] = int(cacheBehaviorDict["MinTTL"])
            if not isinstance(cacheBehaviorDict["MinTTL"], int):
                raise TypeError(
                    f"'MinTTL' in 'CacheBehavior' must be of type int. it is number of seconds for MinTTL. default is 0. got: {type(cacheBehaviorDict['MinTTL'])}")
            if cacheBehaviorDict["MinTTL"] < 0:
                raise ValueError(
                    f"'MinTTL' in 'CacheBehavior' cannot be negative. got: {cacheBehaviorDict['MinTTL']}")
            if cacheBehaviorDict["MinTTL"] > 31536000:
                raise ValueError(
                    f"'MinTTL' in 'CacheBehavior' cannot be > 31536000 seconds (1y). got: {cacheBehaviorDict['MinTTL']}")
            instantiate_args["MinTTL"] = cacheBehaviorDict["MinTTL"]
        else:
            instantiate_args["MinTTL"] = cls.MinTTL

        if "DefaultTTL" in cacheBehaviorDict.keys():
            if isinstance(cacheBehaviorDict["DefaultTTL"], str):
                cacheBehaviorDict["DefaultTTL"] = int(cacheBehaviorDict["DefaultTTL"])
            if not isinstance(cacheBehaviorDict["DefaultTTL"], int):
                raise TypeError(
                    f"'DefaultTTL' in 'CacheBehavior' must be of type int. it is number of seconds for DefaultTTL. default is 86400 (1d). got: {type(cacheBehaviorDict['DefaultTTL'])}")
            if cacheBehaviorDict["DefaultTTL"] < 0:
                raise ValueError(
                    f"'DefaultTTL' in 'DefaultCacheBehavior' cannot be negative. got: {cacheBehaviorDict['DefaultTTL']}")
            if cacheBehaviorDict["DefaultTTL"] > 31536000:
                raise ValueError(
                    f"'DefaultTTL' in 'DefaultCacheBehavior' cannot be > 31536000 seconds (1y). got: {cacheBehaviorDict['DefaultTTL']}")
            instantiate_args["DefaultTTL"] = cacheBehaviorDict["DefaultTTL"]
        else:
            instantiate_args["DefaultTTL"] = cls.DefaultTTL

        if "MaxTTL" in cacheBehaviorDict.keys():
            if isinstance(cacheBehaviorDict["MaxTTL"], str):
                cacheBehaviorDict["MaxTTL"] = int(cacheBehaviorDict["MaxTTL"])
            if not isinstance(cacheBehaviorDict["MaxTTL"], int):
                raise TypeError(
                    f"'MaxTTL' in 'CacheBehavior' must be of type int. it is number of seconds for MaxTTL. default is 0. got: {type(cacheBehaviorDict['MaxTTL'])}")
            if cacheBehaviorDict["MaxTTL"] < 0:
                raise ValueError(
                    f"'MaxTTL' in 'CacheBehavior' cannot be negative. got: {cacheBehaviorDict['MaxTTL']}")
            if cacheBehaviorDict["MaxTTL"] > 31536000:
                raise ValueError(
                    f"'MaxTTL' in 'CacheBehavior' cannot be > 31536000 seconds (1y). got: {cacheBehaviorDict['MaxTTL']}")
            instantiate_args["MaxTTL"] = cacheBehaviorDict["MaxTTL"]
        else:
            instantiate_args["MaxTTL"] = cls.MaxTTL

        if instantiate_args["MinTTL"] > instantiate_args["MaxTTL"]:
            raise ValueError(
                f"'MinTTL' cannot be greater than 'MaxTTL' in 'CacheBehavior'. got MinTTL: {instantiate_args['MinTTL']} > MaxTTL: {instantiate_args['MaxTTL']}")

        allowedMethods = None
        cachedMethods = None
        if "AllowedMethods" in cacheBehaviorDict.keys():
            if not isinstance(cacheBehaviorDict["AllowedMethods"], list):
                raise TypeError(
                    f"'AllowedMethods' in 'CacheBehavior' must be a list (of strings). got: {type(cacheBehaviorDict['AllowedMethods'])}")
            allowedMethods = cacheBehaviorDict["AllowedMethods"]
        if "CachedMethods" in cacheBehaviorDict.keys():
            if not isinstance(cacheBehaviorDict["CachedMethods"], list):
                raise TypeError(
                    f"'CachedMethods' in 'CacheBehavior' must be a list (of strings). got: {type(cacheBehaviorDict['CachedMethods'])}")
            cachedMethods = cacheBehaviorDict["CachedMethods"]

        if allowedMethods is not None or cachedMethods is not None:
            instantiate_args["AllowedMethods"] = AllowedMethods.from_cfn_form(allowedMethodsList=allowedMethods,
                                                                              cachedMethodsList=cachedMethods)
        # we'll provide defaults, though not explicitly required to by api for consistency in object form for comparisons
        else:
            defaultAllowed = AllowedMethods(Quantity=2, Items=["GET", "HEAD"],
                                            CachedMethods=StringListItems.from_cfn_form(itemsList=["GET", "HEAD"]))
            instantiate_args["AllowedMethods"] = defaultAllowed

        if "SmoothStreaming" in cacheBehaviorDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(cacheBehaviorDict["SmoothStreaming"], str):
                try:
                    smoothStreaming_bool = str2bool(cacheBehaviorDict["SmoothStreaming"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'CacheBehavior' 'SmoothStreaming' state to boolean. got: {cacheBehaviorDict['SmoothStreaming']}"
                        f"{str(CastEx)}")
                instantiate_args["SmoothStreaming"] = smoothStreaming_bool
            elif isinstance(cacheBehaviorDict["SmoothStreaming"], bool):
                instantiate_args["SmoothStreaming"] = cacheBehaviorDict["SmoothStreaming"]
            else:
                raise TypeError(
                    f"'SmoothStreaming' in 'CacheBehavior' must be of type str (cast) or bool. got {type(cacheBehaviorDict['SmoothStreaming'])}")
        else:
            instantiate_args["SmoothStreaming"] = False

        if "Compress" in cacheBehaviorDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(cacheBehaviorDict["Compress"], str):
                try:
                    compress_bool = str2bool(cacheBehaviorDict["Compress"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'CacheBehavior' 'Compress' state to boolean. got: {cacheBehaviorDict['Compress']}"
                        f"{str(CastEx)}")
                instantiate_args["Compress"] = compress_bool
            elif isinstance(cacheBehaviorDict["Compress"], bool):
                instantiate_args["Compress"] = cacheBehaviorDict["Compress"]
            else:
                raise TypeError(
                    f"'Compress' in 'CacheBehavior' must be of type str (cast) or bool. got {type(cacheBehaviorDict['Compress'])}")
        else:
            instantiate_args["Compress"] = False

        if "LambdaFunctionAssociations" in cacheBehaviorDict.keys():
            if not isinstance(cacheBehaviorDict["LambdaFunctionAssociations"], list):
                raise TypeError(
                    f"'LambdaFunctionAssociations' in 'CacheBehavior' must be of type list (of dict). got: {type(cacheBehaviorDict['LambdaFunctionAssociations'])}")
            instantiate_args["LambdaFunctionAssociations"] = LambdaFunctionAssociations.from_cfn_form(
                cacheBehaviorDict["LambdaFunctionAssociations"])
        else:
            instantiate_args["LambdaFunctionAssociations"] = LambdaFunctionAssociations(Quantity=0)
        if "FieldLevelEncryptionId" in cacheBehaviorDict.keys():
            if not isinstance(cacheBehaviorDict["FieldLevelEncryptionId"], str):
                raise TypeError(
                    f"'FieldLevelEncryptionId' in 'CacheBehavior' must be of type string. got: {type(cacheBehaviorDict['FieldLevelEncryptionId'])}")
            instantiate_args["FieldLevelEncryptionId"] = cacheBehaviorDict["FieldLevelEncryptionId"]
        else:
            instantiate_args["FieldLevelEncryptionId"] = cls.FieldLevelEncryptionId

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"PathPattern": self.PathPattern, "TargetOriginId": self.TargetOriginId,
                  "ForwardedValues": self.ForwardedValues.to_dict(), "ViewerProtocolPolicy": self.ViewerProtocolPolicy,
                  "TrustedSigners": self.TrustedSigners.to_dict(), "MinTTL": self.MinTTL, "DefaultTTL": self.DefaultTTL,
                  "MaxTTL": self.MaxTTL, "AllowedMethods": self.AllowedMethods.to_dict(),
                  "SmoothStreaming": self.SmoothStreaming, "Compress": self.Compress}
        if self.LambdaFunctionAssociations is not None:
            retval["LambdaFunctionAssociations"] = self.LambdaFunctionAssociations.to_dict()
        retval["FieldLevelEncryptionId"] = self.FieldLevelEncryptionId
        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class DefaultCacheBehavior:
    # N.B. there is no 'path pattern' on a default cache behavior obj
    TargetOriginId: str  # cfn: required, api: required
    ForwardedValues: ForwardedValues  # cfn: required, api: required
    ViewerProtocolPolicy: str  # cfn: required, api: required
    TrustedSigners: Optional[
        TrustedSigners] = None  # cfn: OPTIONAL (cfn docs inaccurate, appears to be list of what ends up in 'items'), api: required
    MinTTL: Optional[
        int] = 0  # cfn: OPTIONAL, # cfn: OPTIONAL, api: required - You must specify 0 for MinTTL if you configure CloudFront to forward all headers to your origin (under Headers , if you specify 1 for Quantity and * for Name). default: 0
    DefaultTTL: Optional[int] = 86400  # cfn: OPTIONAL, api: OPTIONAL. default 1d in seconds
    MaxTTL: Optional[int] = 31536000  # cfn: OPTIONAL, api: OPTIONAL. default 1y in seconds
    AllowedMethods: Optional[
        AllowedMethods] = None  # cfn: OPTIONAL, api: OPTIONAL - default appears to be ['GET','HEAD']
    SmoothStreaming: Optional[bool] = False  # cfn: OPTIONAL, api: OPTIONAL - default False
    Compress: Optional[bool] = False  # cfn: OPTIONAL, api: OPTIONAL. default False
    LambdaFunctionAssociations: Optional[LambdaFunctionAssociations] = None
    FieldLevelEncryptionId: Optional[str] = ""  # cfn: OPTIONAL, api: OPTIONAL in creates, REQ in updates

    # absolute max is 31536000 and you'll see odd behavior if a larger value used (see below comment line) - this class with hard reject such large values
    # If you change the value of Minimum TTL or Default TTL to more than 31536000 seconds, then the default value of Maximum TTL changes to the value of Default TTL.

    @classmethod
    def from_cfn_form(cls, defaultCacheBehaviorDict) -> 'DefaultCacheBehavior':
        if not isinstance(defaultCacheBehaviorDict, dict):
            raise TypeError(f"'DefaultCacheBehavior' is expected to be a dict, got: {type(defaultCacheBehaviorDict)}")
        if "TargetOriginId" not in defaultCacheBehaviorDict.keys():
            raise ValueError(f"no 'TargetOriginId' in DefaultCacheBehavior: {defaultCacheBehaviorDict}")
        if not isinstance(defaultCacheBehaviorDict["TargetOriginId"], str):
            raise TypeError(
                f"'TargetOriginId' in 'DefaultCacheBehavior' must be a string. will NOT cast. got: {type(defaultCacheBehaviorDict['TargetOriginId'])}")
        if "ForwardedValues" not in defaultCacheBehaviorDict.keys():
            raise ValueError(f"no 'ForwardedValues' in DefaultCacheBehavior: {defaultCacheBehaviorDict}")
        if not isinstance(defaultCacheBehaviorDict["ForwardedValues"], dict):
            raise TypeError(
                f"'ForwardedValues' in 'DefaultCacheBehavior' must be a dict, got: {type(defaultCacheBehaviorDict['ForwardedValues'])}")
        if "ViewerProtocolPolicy" not in defaultCacheBehaviorDict.keys():
            raise ValueError(f"no 'ViewerProtocolPolicy' in DefaultCacheBehavior: {defaultCacheBehaviorDict}")
        if not isinstance(defaultCacheBehaviorDict["ViewerProtocolPolicy"], str):
            raise TypeError(
                f"'ViewerProtocolPolicy' in 'DefaultCacheBehavior' must be a string. will NOT cast. got: {type(defaultCacheBehaviorDict['ViewerProtocolPolicy'])}")

        instantiate_args = {"TargetOriginId": defaultCacheBehaviorDict["TargetOriginId"],
                            "ForwardedValues": ForwardedValues.from_cfn_form(
                                defaultCacheBehaviorDict["ForwardedValues"]),
                            "ViewerProtocolPolicy": defaultCacheBehaviorDict["ViewerProtocolPolicy"]}
        # trusted signers is a list of strings from cfn, despite the cfn docs being super crazy on the subject and talking to the api form of this data element

        if "TrustedSigners" in defaultCacheBehaviorDict.keys():
            if not isinstance(defaultCacheBehaviorDict["TrustedSigners"], list):
                raise TypeError(
                    f"'TrustedSigners' in 'DefaultCacheBehavior' must be a list. got: {type(defaultCacheBehaviorDict['TrustedSigners'])}")
            instantiate_args["TrustedSigners"] = TrustedSigners.from_cfn_form(
                defaultCacheBehaviorDict["TrustedSigners"])
        else:
            instantiate_args["TrustedSigners"] = TrustedSigners(Enabled=False, Quantity=0)

        if "MinTTL" in defaultCacheBehaviorDict.keys():
            if isinstance(defaultCacheBehaviorDict["MinTTL"], str):
                defaultCacheBehaviorDict["MinTTL"] = int(defaultCacheBehaviorDict["MinTTL"])
            if not isinstance(defaultCacheBehaviorDict["MinTTL"], int):
                raise TypeError(
                    f"'MinTTL' in 'DefaultCacheBehavior' must be of type int. it is number of seconds for MinTTL. default is 0. got: {type(defaultCacheBehaviorDict['MinTTL'])}")
            if defaultCacheBehaviorDict["MinTTL"] < 0:
                raise ValueError(
                    f"'MinTTL' in 'DefaultCacheBehavior' cannot be negative. got: {defaultCacheBehaviorDict['MinTTL']}")
            if defaultCacheBehaviorDict["MinTTL"] > 31536000:
                raise ValueError(
                    f"'MinTTL' in 'DefaultCacheBehavior' cannot be > 31536000 seconds (1y). got: {defaultCacheBehaviorDict['MinTTL']}")
            instantiate_args["MinTTL"] = defaultCacheBehaviorDict["MinTTL"]
        else:
            instantiate_args["MinTTL"] = cls.MinTTL

        if "DefaultTTL" in defaultCacheBehaviorDict.keys():
            if isinstance(defaultCacheBehaviorDict["DefaultTTL"], str):
                defaultCacheBehaviorDict["DefaultTTL"] = int(defaultCacheBehaviorDict["DefaultTTL"])
            if not isinstance(defaultCacheBehaviorDict["DefaultTTL"], int):
                raise TypeError(
                    f"'DefaultTTL' in 'DefaultCacheBehavior' must be of type int. it is number of seconds for DefaultTTL. default is 86400 (1d). got: {type(defaultCacheBehaviorDict['DefaultTTL'])}")
            if defaultCacheBehaviorDict["DefaultTTL"] < 0:
                raise ValueError(
                    f"'DefaultTTL' in 'DefaultCacheBehavior' cannot be negative. got: {defaultCacheBehaviorDict['DefaultTTL']}")
            if defaultCacheBehaviorDict["DefaultTTL"] > 31536000:
                raise ValueError(
                    f"'DefaultTTL' in 'DefaultCacheBehavior' cannot be > 31536000 seconds (1y). got: {defaultCacheBehaviorDict['DefaultTTL']}")
            instantiate_args["DefaultTTL"] = defaultCacheBehaviorDict["DefaultTTL"]
        else:
            instantiate_args["DefaultTTL"] = cls.DefaultTTL

        if "MaxTTL" in defaultCacheBehaviorDict.keys():
            if isinstance(defaultCacheBehaviorDict["MaxTTL"], str):
                defaultCacheBehaviorDict["MaxTTL"] = int(defaultCacheBehaviorDict["MaxTTL"])
            if not isinstance(defaultCacheBehaviorDict["MaxTTL"], int):
                raise TypeError(
                    f"'MaxTTL' in 'DefaultCacheBehavior' must be of type int. it is number of seconds for MaxTTL. default is 0. got: {type(defaultCacheBehaviorDict['MaxTTL'])}")
            if defaultCacheBehaviorDict["MaxTTL"] < 0:
                raise ValueError(
                    f"'MaxTTL' in 'DefaultCacheBehavior' cannot be negative. got: {defaultCacheBehaviorDict['MaxTTL']}")
            if defaultCacheBehaviorDict["MaxTTL"] > 31536000:
                raise ValueError(
                    f"'MaxTTL' in 'DefaultCacheBehavior' cannot be > 31536000 seconds (1y). got: {defaultCacheBehaviorDict['MaxTTL']}")
            instantiate_args["MaxTTL"] = defaultCacheBehaviorDict["MaxTTL"]
        else:
            instantiate_args["MaxTTL"] = cls.MaxTTL

        if instantiate_args["MinTTL"] > instantiate_args["MaxTTL"]:
            raise ValueError(
                f"'MinTTL' cannot be greater than 'MaxTTL' in 'DefaultCacheBehavior'. got MinTTL: {instantiate_args['MinTTL']} > MaxTTL: {instantiate_args['MaxTTL']}")

        allowedMethods = None
        cachedMethods = None
        if "AllowedMethods" in defaultCacheBehaviorDict.keys():
            if not isinstance(defaultCacheBehaviorDict["AllowedMethods"], list):
                raise TypeError(
                    f"'AllowedMethods' in 'DefaultCacheBehavior' must be a list (of strings). got: {type(defaultCacheBehaviorDict['AllowedMethods'])}")
            allowedMethods = defaultCacheBehaviorDict["AllowedMethods"]
        if "CachedMethods" in defaultCacheBehaviorDict.keys():
            if not isinstance(defaultCacheBehaviorDict["CachedMethods"], list):
                raise TypeError(
                    f"'CachedMethods' in 'DefaultCacheBehavior' must be a list (of strings). got: {type(defaultCacheBehaviorDict['CachedMethods'])}")
            cachedMethods = defaultCacheBehaviorDict["CachedMethods"]

        if allowedMethods is not None or cachedMethods is not None:
            instantiate_args["AllowedMethods"] = AllowedMethods.from_cfn_form(allowedMethodsList=allowedMethods,
                                                                              cachedMethodsList=cachedMethods)
        # we'll provide defaults, though not explicitly required to by api for consistency in object form for comparisons
        else:
            defaultAllowed = AllowedMethods(Quantity=2, Items=["GET", "HEAD"],
                                            CachedMethods=StringListItems.from_cfn_form(itemsList=["GET", "HEAD"]))
            instantiate_args["AllowedMethods"] = defaultAllowed

        if "SmoothStreaming" in defaultCacheBehaviorDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(defaultCacheBehaviorDict["SmoothStreaming"], str):
                try:
                    smoothStreaming_bool = str2bool(defaultCacheBehaviorDict["SmoothStreaming"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'DefaultCacheBehavior' 'SmoothStreaming' state to boolean. got: {defaultCacheBehaviorDict['SmoothStreaming']}"
                        f"{str(CastEx)}")
                instantiate_args["SmoothStreaming"] = smoothStreaming_bool
            elif isinstance(defaultCacheBehaviorDict["SmoothStreaming"], bool):
                instantiate_args["SmoothStreaming"] = defaultCacheBehaviorDict["SmoothStreaming"]
            else:
                raise TypeError(
                    f"'SmoothStreaming' in 'DefaultCacheBehavior' must be of type str (cast) or bool. got {type(defaultCacheBehaviorDict['SmoothStreaming'])}")
        else:
            instantiate_args["SmoothStreaming"] = False

        if "Compress" in defaultCacheBehaviorDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(defaultCacheBehaviorDict["Compress"], str):
                try:
                    compress_bool = str2bool(defaultCacheBehaviorDict["Compress"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'DefaultCacheBehavior' 'Compress' state to boolean. got: {defaultCacheBehaviorDict['Compress']}"
                        f"{str(CastEx)}")
                instantiate_args["Compress"] = compress_bool
            elif isinstance(defaultCacheBehaviorDict["Compress"], bool):
                instantiate_args["Compress"] = defaultCacheBehaviorDict["Compress"]
            else:
                raise TypeError(
                    f"'Compress' in 'DefaultCacheBehavior' must be of type str (cast) or bool. got {type(defaultCacheBehaviorDict['Compress'])}")
        else:
            instantiate_args["Compress"] = False

        if "LambdaFunctionAssociations" in defaultCacheBehaviorDict.keys():
            if not isinstance(defaultCacheBehaviorDict["LambdaFunctionAssociations"], list):
                raise TypeError(
                    f"'LambdaFunctionAssociations' in 'DefaultCacheBehavior' must be of type list (of dict). got: {type(defaultCacheBehaviorDict['LambdaFunctionAssociations'])}")
            instantiate_args["LambdaFunctionAssociations"] = LambdaFunctionAssociations.from_cfn_form(
                defaultCacheBehaviorDict["LambdaFunctionAssociations"])
        else:
            instantiate_args["LambdaFunctionAssociations"] = LambdaFunctionAssociations(Quantity=0)
        if "FieldLevelEncryptionId" in defaultCacheBehaviorDict.keys():
            if not isinstance(defaultCacheBehaviorDict["FieldLevelEncryptionId"], str):
                raise TypeError(
                    f"'FieldLevelEncryptionId' in 'DefaultCacheBehavior' must be of type string. got: {type(defaultCacheBehaviorDict['FieldLevelEncryptionId'])}")
            instantiate_args["FieldLevelEncryptionId"] = defaultCacheBehaviorDict["FieldLevelEncryptionId"]
        else:
            instantiate_args["FieldLevelEncryptionId"] = cls.FieldLevelEncryptionId

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"TargetOriginId": self.TargetOriginId, "ForwardedValues": self.ForwardedValues.to_dict(),
                  "ViewerProtocolPolicy": self.ViewerProtocolPolicy, "TrustedSigners": self.TrustedSigners.to_dict(),
                  "MinTTL": self.MinTTL, "DefaultTTL": self.DefaultTTL, "MaxTTL": self.MaxTTL,
                  "AllowedMethods": self.AllowedMethods.to_dict(), "SmoothStreaming": self.SmoothStreaming,
                  "Compress": self.Compress}
        if self.LambdaFunctionAssociations is not None:
            retval["LambdaFunctionAssociations"] = self.LambdaFunctionAssociations.to_dict()
        retval["FieldLevelEncryptionId"] = self.FieldLevelEncryptionId
        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CacheBehaviors:
    Quantity: int
    Items: Optional[List[CacheBehavior]] = None

    @classmethod
    def from_cfn_form(cls, cacheBehaviorsList) -> 'CacheBehaviors':
        if not isinstance(cacheBehaviorsList, list):
            raise TypeError(f"'CacheBehaviors' must be of type list. got: {type(cacheBehaviorsList)}")
        if len(cacheBehaviorsList) == 0:
            return cls(Quantity=0)

        items = [CacheBehavior.from_cfn_form(i) for i in cacheBehaviorsList]
        return cls(Quantity=len(items), Items=items)

    def to_dict(self):
        if self.Items is None:
            return {"Quantity": 0}
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CustomErrorResponse:
    ErrorCode: int
    ResponsePagePath: Optional[str] = None
    ResponseCode: Optional[str] = None
    ErrorCachingMinTTL: Optional[
        int] = 300  # 5m by default (ref: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/HTTPStatusCodes.html)

    @classmethod
    def from_cfn_form(cls, customErrorResponseDict) -> 'CustomErrorResponse':
        if not isinstance(customErrorResponseDict, dict):
            raise TypeError(f"'CustomErrorResponse' must be of type dict. got: {type(customErrorResponseDict)}")
        if "ErrorCode" not in customErrorResponseDict.keys():
            raise ValueError(f"'CustomErrorResponse' dict must include key 'ErrorCode': {customErrorResponseDict}")

        if isinstance(customErrorResponseDict["ErrorCode"], str):
            customErrorResponseDict["ErrorCode"] = int(customErrorResponseDict["ErrorCode"])

        instantiate_args = {}
        instantiate_args["ErrorCode"] = customErrorResponseDict["ErrorCode"]

        if "ResponsePagePath" in customErrorResponseDict.keys():
            if not isinstance(customErrorResponseDict["ResponsePagePath"], str):
                raise TypeError(
                    f"'ResponsePagePath' in 'CustomErrorResponse' must be of type str. got {type(customErrorResponseDict['ResponsePagePath'])}")
            # if there's a ResponsePagePath there needs to be a ResponseCode
            if "ResponseCode" not in customErrorResponseDict.keys():
                raise ValueError(
                    f"if 'ResponsePagePath' specified in 'CustomErrorResponse' key 'ResponseCode' must exist also. got: {customErrorResponseDict}'")
            instantiate_args["ResponsePagePath"] = customErrorResponseDict["ResponsePagePath"]

        if "ResponseCode" in customErrorResponseDict.keys():
            if not isinstance(customErrorResponseDict["ResponseCode"], str):
                # boto3 wants this as a string, but cfn wise its an int
                customErrorResponseDict["ResponseCode"] = str(customErrorResponseDict["ResponseCode"])
            # if there's a ResponseCode there needs to be a ResponsePagePath
            if "ResponsePagePath" not in customErrorResponseDict.keys():
                raise ValueError(
                    f"if 'ResponseCode' specified in 'CustomErrorResponse' key 'ResponsePagePath' must exist also. got: {customErrorResponseDict}'")
            instantiate_args["ResponseCode"] = customErrorResponseDict["ResponseCode"]

        if "ErrorCachingMinTTL" in customErrorResponseDict.keys():
            if isinstance(customErrorResponseDict["ErrorCachingMinTTL"], str):
                customErrorResponseDict["ErrorCachingMinTTL"] = int(customErrorResponseDict["ErrorCachingMinTTL"])
            if not isinstance(customErrorResponseDict["ErrorCachingMinTTL"], int):
                raise TypeError(
                    f"'ErrorCachingMinTTL' in 'CustomErrorResponse' must be of type int. it is number of seconds for MinTTL. default is 300. got: {type(customErrorResponseDict['ErrorCachingMinTTL'])}")
            if customErrorResponseDict["ErrorCachingMinTTL"] < 0:
                raise ValueError(
                    f"'ErrorCachingMinTTL' in 'CustomErrorResponse' cannot be negative. got: {customErrorResponseDict['ErrorCachingMinTTL']}")
            if customErrorResponseDict["ErrorCachingMinTTL"] > 31536000:
                raise ValueError(
                    f"'ErrorCachingMinTTL' in 'CustomErrorResponse' cannot be > 31536000 seconds (1y). got: {customErrorResponseDict['ErrorCachingMinTTL']}")
            instantiate_args["ErrorCachingMinTTL"] = customErrorResponseDict["ErrorCachingMinTTL"]
        else:
            instantiate_args["ErrorCachingMinTTL"] = cls.ErrorCachingMinTTL

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"ErrorCode": self.ErrorCode}

        if self.ResponsePagePath is not None:
            if self.ResponseCode is None:
                raise ValueError(
                    f"invalid 'CustomErrorResponse' object. if 'ResponsePagePath' is non-null, so must be 'ResponseCode'")
            retval["ResponsePagePath"] = self.ResponsePagePath
        if self.ResponseCode is not None:
            if self.ResponsePagePath is None:
                raise ValueError(
                    f"invalid 'CustomErrorResponse' object. if 'ResponseCode' is non-null, so must be 'ResponsePagePath'")
            retval["ResponseCode"] = self.ResponseCode
        retval["ErrorCachingMinTTL"] = self.ErrorCachingMinTTL
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CustomErrorResponses:
    Quantity: int
    Items: Optional[List[CustomErrorResponse]] = None

    @classmethod
    def from_cfn_form(cls, customErrorResponsesList) -> 'CustomErrorResponses':
        if not isinstance(customErrorResponsesList, list):
            raise TypeError(f"'CustomErrorResponses' must be of type list. got: {type(customErrorResponsesList)}")
        if len(customErrorResponsesList) == 0:
            return cls(Quantity=0)

        items = [CustomErrorResponse.from_cfn_form(i) for i in customErrorResponsesList]
        return cls(Quantity=len(items), Items=items)

    def to_dict(self):
        if self.Items is None:
            return {"Quantity": 0}
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()

@dataclass
class Logging:
    Bucket: str
    Enabled: Optional[bool] = True
    IncludeCookies: Optional[bool] = False
    Prefix: Optional[str] = ""

    @classmethod
    def from_cfn_form(cls, loggingDict) -> 'Logging':
        if not isinstance(loggingDict, dict):
            raise TypeError(f"'Logging' must be for type dict. got: {type(loggingDict)}")

        if "Bucket" not in loggingDict.keys():
            raise ValueError(f"'Logging' dict must contain key 'Bucket'. got: {loggingDict}")

        instantiate_args = {"Bucket": loggingDict["Bucket"]}

        if "Enabled" in loggingDict.keys():
            if isinstance(loggingDict["Enabled"], str):
                try:
                    enabled_bool = str2bool(loggingDict["Enabled"])
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'DistributionConfig' 'Logging' 'Enabled' state to boolean. got: {loggingDict['Enabled']}"
                        f"{str(CastEx)}"
                    )
                instantiate_args["Enabled"] = enabled_bool
            if not isinstance(loggingDict["Enabled"], bool):
                raise TypeError(f"'Enabled' in 'Logging' must be of type bool. got: {type(loggingDict['Enabled'])}")
            instantiate_args["Enabled"] = loggingDict["Enabled"]
        else:
            instantiate_args["Enabled"] = cls.Enabled

        if "IncludeCookies" in loggingDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(loggingDict["IncludeCookies"], str):
                try:
                    includeCookies_bool = str2bool(loggingDict["IncludeCookies"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'DistributionConfig' 'Logging' 'IncludeCookies' state to boolean. got: {loggingDict['IncludeCookies']}"
                        f"{str(CastEx)}")
                instantiate_args["IncludeCookies"] = includeCookies_bool
            elif isinstance(loggingDict["IncludeCookies"], bool):
                instantiate_args["IncludeCookies"] = loggingDict["IncludeCookies"]
            else:
                raise TypeError(
                    f"'IncludeCookies' in 'DistributionConfig' must be of type str (cast) or bool. got {type(loggingDict['IncludeCookies'])}")
        else:
            instantiate_args["IncludeCookies"] = cls.IncludeCookies

        if "Prefix" in loggingDict.keys():
            if not isinstance(loggingDict["Prefix"], str):
                raise TypeError(f"'Prefix' in 'Logging' must be of type string. got: {type(loggingDict['Prefix'])}")
            instantiate_args["Prefix"] = loggingDict["Prefix"]
        else:
            instantiate_args["Prefix"] = cls.Prefix

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"Enabled": self.Enabled, "IncludeCookies": self.IncludeCookies, "Bucket": self.Bucket,
                  "Prefix": self.Prefix}
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class StatusCodes:
    Quantity: int
    Items: List[int]

    @classmethod
    def from_cfn_form(cls, statusCodesList) -> 'StatusCodes':
        # !N.B. - a FailoverCriteria['StatusCodes'] list can be empty, but must exist!
        if not isinstance(statusCodesList, list):
            raise TypeError(f"'StatusCodes' is expected to be a list, got: {type(statusCodesList)}")
        items = [int(i) for i in statusCodesList]
        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        return {"Quantity": self.Quantity, "Items": self.Items}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class FailoverCriteria:
    StatusCodes: StatusCodes

    @classmethod
    def from_cfn_form(cls, failoverCriteriaDict) -> 'FailoverCriteria':
        if not isinstance(failoverCriteriaDict, dict):
            raise TypeError(f"'FailoverCriteria' is expected to be a dict, got: {type(failoverCriteriaDict)}")
        if "StatusCodes" not in failoverCriteriaDict.keys():
            raise ValueError(f"No 'StatusCodes' in FailoverCriteria: {failoverCriteriaDict}")
        instantiate_args = {"StatusCodes": StatusCodes.from_cfn_form(failoverCriteriaDict["StatusCodes"])}

        return cls(**instantiate_args)

    def to_dict(self):
        return {"StatusCodes": self.StatusCodes.to_dict()}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class OriginGroupMember:
    OriginId: str

    def to_dict(self):
        return {"OriginId": self.OriginId}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class OriginGroupMembers:
    Quantity: int
    Items: List[OriginGroupMember]

    @classmethod
    def from_cfn_form(cls, originGroupMembersList) -> 'OriginGroupMembers':
        if not isinstance(originGroupMembersList, list):
            raise TypeError(f"(origin group) 'Members' is expected to be a list, got: {type(originGroupMembersList)}")
        if len(originGroupMembersList) == 0:
            raise ValueError("cannot instantiate zero item OriginGroup Members")

        items = []
        for originGroupMember in originGroupMembersList:
            if not isinstance(originGroupMember, str):
                raise TypeError(
                    f"Members list entries of an origin group members list must be strings, will NOT cast. got: {type(originGroupMember)}")
            items.append(OriginGroupMember(originGroupMember))

        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class OriginGroup:
    Id: str
    FailoverCriteria: FailoverCriteria
    Members: OriginGroupMembers

    @classmethod
    def from_cfn_form(cls, originGroupDict) -> 'OriginGroup':
        if not isinstance(originGroupDict, dict):
            raise TypeError(f"An 'Origin Group' entry in Origin Groups must be a dict, got: {type(originGroupDict)}")
        if "Id" not in originGroupDict.keys():
            raise ValueError(f"no 'Id' in OriginGroup: {originGroupDict}")
        if "FailoverCriteria" not in originGroupDict.keys():
            raise ValueError(f"no 'FailoverCriteria' in OriginGroup: {originGroupDict}")
        if "Members" not in originGroupDict.keys():
            raise ValueError(f"no 'OriginGroupMembers' in OriginGroup: {originGroupDict}")

        instantiate_args = {"Id": originGroupDict["Id"],
                            "FailoverCriteria": FailoverCriteria.from_cfn_form(originGroupDict["FailoverCriteria"]),
                            "Members": OriginGroupMembers.from_cfn_form(originGroupDict["Members"])}

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"Id": self.Id, "FailoverCriteria": self.FailoverCriteria.to_dict(), "Members": self.Members.to_dict()}
        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class OriginGroups:
    Quantity: int
    Items: List[OriginGroup]

    @classmethod
    def from_cfn_form(cls, originGroupsList: list) -> 'OriginGroups':
        if not isinstance(originGroupsList, list):
            raise TypeError(
                f"'OriginGroups' must be specified as a list (of dict items). got: {type(originGroupsList)}")
        if len(originGroupsList) == 0:
            raise ValueError("cannot instantiate zero item OriginGroups")

        items = []
        for originGroup in originGroupsList:
            if not isinstance(originGroup, dict):
                raise TypeError(
                    f"'OriginGroups' list items must be of type dict. got: {type(originGroup)}")
            items.append(OriginGroup.from_cfn_form(originGroup))

        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CustomHeadersItem:
    HeaderName: str
    HeaderValue: str

    def to_dict(self):
        return {"HeaderName": self.HeaderName, "HeaderValue": self.HeaderValue}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CustomHeaders:
    Quantity: int
    Items: Optional[List[CustomHeadersItem]] = None

    @classmethod
    def from_cfn_form(cls, customHeadersList: list) -> 'CustomHeaders':
        # N.B. ! in cfn its a list on the origin "OriginCustomHeaders" while in boto3 its "CustomHeaders"

        if not isinstance(customHeadersList, list):
            raise TypeError(f"'OriginCustomHeaders' is expected to be a list. got: {type(customHeadersList)}")
        if len(customHeadersList) == 0:
            return cls(Quantity=0)
        items = []
        for customHeaderItem in customHeadersList:
            if not isinstance(customHeaderItem, dict):
                raise TypeError(f"'OriginCustomHeaders' list items must be of type dict. got: {type(customHeaderItem)}")
            if "HeaderName" not in customHeaderItem.keys():
                raise ValueError(f"origin custom header entry missing 'HeaderName': {customHeadersList}")
            if "HeaderValue" not in customHeaderItem.keys():
                raise ValueError(f"origin custom header entry missing 'HeaderValue': {customHeadersList}")
            items.append(CustomHeadersItem(HeaderName=customHeaderItem["HeaderName"],
                                           HeaderValue=customHeaderItem["HeaderValue"]))
        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        if self.Items is None:
            return {"Quantity": 0}
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class CustomOriginConfig:
    OriginProtocolPolicy: str
    HTTPPort: Optional[int] = None
    HTTPSPort: Optional[int] = None
    OriginSslProtocols: Optional[OriginSslProtocols] = None
    OriginReadTimeout: Optional[int] = None
    OriginKeepaliveTimeout: Optional[int] = None

    @classmethod
    def from_cfn_form(cls, customOriginConfig: dict) -> 'CustomOriginConfig':
        if not isinstance(customOriginConfig, dict):
            raise TypeError(f"'CustomOriginConfig' must be of type dict. got: {type(customOriginConfig)}")

        if "OriginProtocolPolicy" not in customOriginConfig.keys():
            raise ValueError(f"CustomOriginConfig must specify 'OriginProtocolPolicy': {customOriginConfig}")
        instantiate_args = {"OriginProtocolPolicy": customOriginConfig["OriginProtocolPolicy"]}
        if "HTTPPort" in customOriginConfig.keys():
            instantiate_args["HTTPPort"] = int(customOriginConfig["HTTPPort"])
        else:
            instantiate_args["HTTPPort"] = 80
        if "HTTPSPort" in customOriginConfig.keys():
            instantiate_args["HTTPSPort"] = int(customOriginConfig["HTTPSPort"])
        else:
            instantiate_args["HTTPSPort"] = 443
        if "OriginSslProtocols" in customOriginConfig.keys():
            instantiate_args["OriginSslProtocols"] = OriginSslProtocols.from_cfn_form(
                customOriginConfig["OriginSslProtocols"])
        if "OriginReadTimeout" in customOriginConfig.keys():
            instantiate_args["OriginReadTimeout"] = int(customOriginConfig["OriginReadTimeout"])
        if "OriginKeepaliveTimeout" in customOriginConfig.keys():
            instantiate_args["OriginKeepaliveTimeout"] = int(customOriginConfig["OriginKeepaliveTimeout"])

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"OriginProtocolPolicy": self.OriginProtocolPolicy, "HTTPPort": self.HTTPPort,
                  "HTTPSPort": self.HTTPSPort, "OriginSslProtocols": self.OriginSslProtocols.to_dict(),
                  "OriginReadTimeout": self.OriginReadTimeout, "OriginKeepaliveTimeout": self.OriginKeepaliveTimeout}
        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class S3OriginConfig:
    # can be empty string if not specifying an OriginAccessIdentity
    OriginAccessIdentity: str

    def to_dict(self):
        return {"OriginAccessIdentity": self.OriginAccessIdentity}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Origin:
    Id: str
    DomainName: str
    OriginPath: Optional[str] = ""
    CustomHeaders: Optional[CustomHeaders] = None
    S3OriginConfig: Optional[S3OriginConfig] = None
    CustomOriginConfig: Optional[CustomOriginConfig] = None

    @classmethod
    def from_cfn_form(cls, originDict: dict) -> 'Origin':
        if not isinstance(originDict, dict):
            raise TypeError(f"'Origins' list items must be of type dict. got: {type(originDict)}")
        if "Id" not in originDict.keys():
            raise ValueError(f"no 'Id' in origin: {originDict}")
        if "DomainName" not in originDict.keys():
            raise ValueError(f"no 'DomainName' in origin: {originDict}")

        instantiate_args = {}
        instantiate_args["Id"] = originDict["Id"]
        instantiate_args["DomainName"] = originDict["DomainName"]

        if "OriginPath" in originDict.keys():
            instantiate_args["OriginPath"] = originDict["OriginPath"]
        else:
            instantiate_args["OriginPath"] = cls.OriginPath

        # note that form in boto3 req/response is "CustomHeaders" while in cfn is "OriginCustomHeaders"
        if "OriginCustomHeaders" in originDict.keys():
            instantiate_args["CustomHeaders"] = CustomHeaders.from_cfn_form(originDict["OriginCustomHeaders"])
        else:
            instantiate_args["CustomHeaders"] = CustomHeaders(Quantity=0)
        if "S3OriginConfig" in originDict.keys():
            instantiate_args["S3OriginConfig"] = S3OriginConfig(
                OriginAccessIdentity=originDict["S3OriginConfig"]["OriginAccessIdentity"])

        if "CustomOriginConfig" in originDict.keys():
            instantiate_args["CustomOriginConfig"] = CustomOriginConfig.from_cfn_form(originDict["CustomOriginConfig"])

        instantiate_args = trim_null_keys(instantiate_args)

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"Id": self.Id, "DomainName": self.DomainName}
        if self.OriginPath is not None:
            retval["OriginPath"] = self.OriginPath
        if self.CustomHeaders is not None:
            retval["CustomHeaders"] = self.CustomHeaders.to_dict()
        if self.S3OriginConfig is not None:
            retval["S3OriginConfig"] = self.S3OriginConfig.to_dict()
        if self.CustomOriginConfig is not None:
            retval["CustomOriginConfig"] = self.CustomOriginConfig.to_dict()
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Origins:
    Quantity: int
    Items: List[Origin]

    @classmethod
    def from_cfn_form(cls, originsList: List[dict]) -> 'Origins':
        if not isinstance(originsList, list):
            raise TypeError(f"'Origins' must be of type list (of dict items). got: {type(originsList)}")

        if len(originsList) == 0:
            raise ValueError("cannot instantiate zero item Origins")

        items = []

        for origin in originsList:
            if not isinstance(origin, dict):
                raise TypeError(f"'Origins' list items must be of type dict. got: {type(origin)}")

            items.append(Origin.from_cfn_form(origin))

        return cls(Items=items, Quantity=len(items))

    def to_dict(self):
        retval = {"Quantity": len(self.Items)}
        if len(self.Items) > 0:
            retval["Items"] = [i.to_dict() for i in self.Items]
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class GeoRestrictionItem:
    Quantity: int
    RestrictionType: Optional[str] = 'none'
    Items: Optional[List[str]] = None

    # NOTE - cfn form specifies 'Locations' - which ends up in 'Items' here. same deal, list o' strings (ISO 3166-1-alpha-2 country codes)
    @classmethod
    def from_cfn_form(cls, geoRestrictionDict) -> 'GeoRestrictionItem':
        if not isinstance(geoRestrictionDict, dict):
            raise TypeError(f"'GeoRestriction' must be of type dict. got: {type(geoRestrictionDict)}")
        if "RestrictionType" not in geoRestrictionDict.keys():
            raise ValueError(f"'GeoRestriction' dict must contain key 'RestrictionType'. got: {geoRestrictionDict}")
        if geoRestrictionDict["RestrictionType"] == 'none':
            return cls(Quantity=0)
        # at this point there MUST be a 'Locations' key (from cfn) for either blacklist or whitelisted items
        if "Locations" not in geoRestrictionDict.keys():
            raise ValueError(
                f"if 'RestrictionType' is NOT 'none', 'Locations' must exist as key in 'GeoRestriction' dict. got: {geoRestrictionDict}")
        if not isinstance(geoRestrictionDict["Locations"], list):
            raise TypeError(
                f"'Locations' key value in 'GeoRestriction' must be of type list (of strings). got: {type(geoRestrictionDict['Locations'])}")

        instantiate_args = {"RestrictionType": geoRestrictionDict["RestrictionType"], "Items": geoRestrictionDict[
            "Locations"], "Quantity": len(geoRestrictionDict["Locations"])}
        return cls(**instantiate_args)

    def to_dict(self):
        if self.RestrictionType == 'none':
            return {"RestrictionType": "none", "Quantity": 0}
        if self.Items is None:
            raise AssertionError(f"invalid 'GeoRestriction' - 'RestrictionType' is not 'none' and 'Items' is None")
        # is valid to have whitelist with no items entries? effectively blocking everything. dunno. don't block it.
        retval = {"RestrictionType": self.RestrictionType, "Quantity": len(self.Items), "Items": self.Items}
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Restrictions:
    GeoRestriction: Optional[GeoRestrictionItem] = GeoRestrictionItem(Quantity=0)

    @classmethod
    def from_cfn_form(cls, restrictionsDict) -> 'Restrictions':
        if not isinstance(restrictionsDict, dict):
            raise TypeError(f"'Restrictions' must be of type dict. got: {type(restrictionsDict)}")
        if "GeoRestriction" not in restrictionsDict.keys():
            raise ValueError(f"'GeoRestriction' key must be present in 'Restrictions' dict. got: {restrictionsDict}")
        if not isinstance(restrictionsDict["GeoRestriction"], dict):
            raise TypeError(
                f"'GeoRestriction' in 'Restrictions' must be of type dict. got: {type(restrictionsDict['GeoRestriction'])}")

        return cls(GeoRestriction=GeoRestrictionItem.from_cfn_form(restrictionsDict["GeoRestriction"]))

    def to_dict(self):
        return {"GeoRestriction": self.GeoRestriction.to_dict()}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class ViewerCertificate:
    CloudFrontDefaultCertificate: Optional[bool] = None
    IAMCertificateId: Optional[str] = None
    ACMCertificateArn: Optional[str] = None
    SSLSupportMethod: Optional[str] = None
    MinimumProtocolVersion: Optional[str] = "TLSv1.1_2016"

    # Certificate: Optional[str] = None   #  deprecated: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags
    # CertificateSource: Optional[str] = None  # deprecated: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags

    @classmethod
    def from_cfn_form(cls, viewerCertificateDict) -> 'ViewerCertificate':
        if not isinstance(viewerCertificateDict, dict):
            raise TypeError(f"'ViewerCertificate' must be of type dict. got: {type(viewerCertificateDict)}")

        oneOfThese = ["AcmCertificateArn", "CloudFrontDefaultCertificate", "IamCertificateId"]
        c = Counter(viewerCertificateDict.keys())
        occurs = sum(c[v] for v in set(oneOfThese))

        if occurs < 1:
            raise ValueError(
                f"'ViewerCertificate' dict must contain ONE of 'AcmCertificateArn', 'CloudFrontDefaultCertificate', 'IamCertificateId'. got none: {viewerCertificateDict}")
        if occurs > 1:
            raise ValueError(
                f"'ViewerCertificate' dict must contain ONE of 'AcmCertificateArn', 'CloudFrontDefaultCertificate', 'IamCertificateId'. got {occurs}: {viewerCertificateDict}")

        instantiate_args = {}

        if "CloudFrontDefaultCertificate" in viewerCertificateDict.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(viewerCertificateDict["CloudFrontDefaultCertificate"], str):
                try:
                    cFrontDefaultCert_bool = str2bool(viewerCertificateDict["CloudFrontDefaultCertificate"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'ViewerCertificate' 'CloudFrontDefaultCertificate' state to boolean. got: {viewerCertificateDict['CloudFrontDefaultCertificate']}"
                        f"{str(CastEx)}")
                instantiate_args["CloudFrontDefaultCertificate"] = cFrontDefaultCert_bool
            elif isinstance(viewerCertificateDict["CloudFrontDefaultCertificate"], bool):
                instantiate_args["CloudFrontDefaultCertificate"] = viewerCertificateDict["CloudFrontDefaultCertificate"]
            else:
                raise TypeError(
                    f"'CloudFrontDefaultCertificate' in 'ViewerCertificate' must be of type str (cast) or bool. got {type(viewerCertificateDict['CloudFrontDefaultCertificate'])}")

            if "SslSupportMethod" in viewerCertificateDict.keys():
                raise ValueError(
                    f"'SslSupportMethod' must NOT be specified when 'CloudFrontDefaultCertificate' exists in 'ViewerCertificate'. got: {viewerCertificateDict}")

        # note it's AcmCertificateArn in cfn, per https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-viewercertificate.html
        if "AcmCertificateArn" in viewerCertificateDict.keys():
            if not isinstance(viewerCertificateDict["AcmCertificateArn"], str):
                raise TypeError(
                    f"'AcmCertificateArn' must be of type string. got: {type(viewerCertificateDict['AcmCertificateArn'])}")

            if "SslSupportMethod" not in viewerCertificateDict.keys():
                raise ValueError(
                    f"'SslSupportMethod' must be specified when 'AcmCertificateArn' exists in 'ViewerCertificate'. got: {viewerCertificateDict}")

            instantiate_args["ACMCertificateArn"] = viewerCertificateDict["AcmCertificateArn"]

        # note it's IamCertificateId in cfn, per https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-viewercertificate.html
        if "IamCertificateId" in viewerCertificateDict.keys():
            if not isinstance(viewerCertificateDict["IamCertificateId"], str):
                raise TypeError(
                    f"'IamCertificateId' must be of type string. got: {type(viewerCertificateDict['IamCertificateId'])}")

            if "SslSupportMethod" not in viewerCertificateDict.keys():
                raise ValueError(
                    f"'SslSupportMethod' must be specified when 'IamCertificateId' exists in 'ViewerCertificate'. got: {viewerCertificateDict}")

            instantiate_args["IAMCertificateId"] = viewerCertificateDict["IamCertificateId"]

        # note it's SslSupportMethod in cfn, per https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-viewercertificate.html
        if "SslSupportMethod" in viewerCertificateDict.keys():
            if not isinstance(viewerCertificateDict["SslSupportMethod"], str):
                raise TypeError(
                    f"'SslSupportMethod' in 'ViewerCertificate' must of type string. got: {type(viewerCertificateDict['SslSupportMethod'])}")

            instantiate_args["SSLSupportMethod"] = viewerCertificateDict["SslSupportMethod"]

        if "MinimumProtocolVersion" in viewerCertificateDict.keys():
            if not isinstance(viewerCertificateDict["MinimumProtocolVersion"], str):
                raise TypeError(
                    f"'MinimumProtocolVersion' in 'ViewerCertificate' must of type string. got: {type(viewerCertificateDict['MinimumProtocolVersion'])}")
            instantiate_args["MinimumProtocolVersion"] = viewerCertificateDict["MinimumProtocolVersion"]
        else:
            if "CloudFrontDefaultCertificate" in viewerCertificateDict.keys():
                instantiate_args[
                    "MinimumProtocolVersion"] = "TLSv1"  # per: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-viewercertificate.html
            else:
                instantiate_args[
                    "MinimumProtocolVersion"] = cls.MinimumProtocolVersion  # per: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags

        return cls(**instantiate_args)

    def to_dict(self):
        retval = {"CloudFrontDefaultCertificate": self.CloudFrontDefaultCertificate,
                  "IAMCertificateId": self.IAMCertificateId, "ACMCertificateArn": self.ACMCertificateArn,
                  "SSLSupportMethod": self.SSLSupportMethod, "MinimumProtocolVersion": self.MinimumProtocolVersion}
        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()

# ref: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-overview-required-fields.html
@dataclass
class DistributionConfig:
    CallerReference: str
    Origins: Origins
    Enabled: bool
    Aliases: Optional[StringListItems] = None  # if nothing need empty for updates
    DefaultRootObject: Optional[str] = ""  # needed on updates
    OriginGroups: Optional[OriginGroups] = None
    DefaultCacheBehavior: Optional[DefaultCacheBehavior] = None
    CacheBehaviors: Optional[CacheBehaviors] = None  # if nothing need empty for updates
    CustomErrorResponses: Optional[CustomErrorResponses] = None  # if nothing need empty for updates
    Comment: Optional[str] = ""
    Logging: Optional[Logging] = None  # if nothing need default/off for updates
    PriceClass: Optional[str] = "PriceClass_All"
    ViewerCertificate: Optional[ViewerCertificate] = None  # if nothing need default here
    Restrictions: Optional[Restrictions] = None
    WebACLId: Optional[str] = ""
    HttpVersion: Optional[str] = "http2"
    IsIPV6Enabled: Optional[bool] = True

    @classmethod
    def from_cfn_form(cls, distroConfig: dict) -> 'DistributionConfig':
        if not isinstance(distroConfig, dict):
            raise TypeError(f"'DistributionConfig' is expected to be a dictionary, got: {type(distroConfig)}")
        instantiate_args = {}
        if "Enabled" not in distroConfig.keys():
            raise ValueError("'Enabled' must exist as key in 'DistributionConfig'")

        # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
        if isinstance(distroConfig["Enabled"], str):
            try:
                enabled_bool = str2bool(distroConfig["Enabled"], raise_exc=True)
            except Exception as CastEx:
                raise ValueError(f"unable to cast string for 'DistributionConfig' 'Enabled' state to boolean. got: {distroConfig['Enabled']}"
                                 f"{str(CastEx)}")
            instantiate_args["Enabled"] = enabled_bool
        elif isinstance(distroConfig["Enabled"], bool):
            instantiate_args["Enabled"] = distroConfig["Enabled"]
        else:
            raise TypeError(
                f"'Enabled' in 'DistributionConfig' must be of type str (cast) or bool. got {type(distroConfig['Enabled'])}")
        if "CallerReference" in distroConfig.keys():
            if not isinstance(distroConfig["CallerReference"], str):
                raise ValueError(
                    "CallerReference must be a unique value (for example, a date-time stamp) that ensures that the request can't be replayed. ref:"
                    "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags")
            instantiate_args["CallerReference"] = distroConfig["CallerReference"]
        else:
            instantiate_args["CallerReference"] = generate_caller_reference()
        if "Aliases" in distroConfig.keys():
            if isinstance(distroConfig["Aliases"], list):
                if len(distroConfig["Aliases"]) > 0:
                    instantiate_args["Aliases"] = StringListItems.from_cfn_form(itemsList=distroConfig["Aliases"])
                else:
                    instantiate_args["Aliases"] = StringListItems(Quantity=0)
            else:
                raise ValueError(
                    "distribution config aliases must be a List[str]. specify as if making cfn AWS::CloudFront::Distribution DistributionConfig. ref:"
                    "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-distributionconfig.html")
        else:
            instantiate_args["Aliases"] = StringListItems.from_cfn_form([])
        if "DefaultRootObject" in distroConfig.keys():
            if not isinstance(distroConfig["DefaultRootObject"], str):
                raise TypeError("if DefaultRootObject is specified, it must be a string, it may be empty")
            instantiate_args["DefaultRootObject"] = distroConfig["DefaultRootObject"]
        else:
            instantiate_args["DefaultRootObject"] = cls.DefaultRootObject
        if "Origins" in distroConfig.keys():
            if not isinstance(distroConfig["Origins"], list):
                raise TypeError(f"'Origins' is expected to be a list, got: {type(distroConfig['Origins'])}")
            if not len(distroConfig["Origins"]) > 0:
                raise ValueError("'Origins' cannot be zero length list")
            instantiate_args["Origins"] = Origins.from_cfn_form(originsList=distroConfig["Origins"])
        else:
            raise ValueError("distro config must contain 'Origins'. ref:"
                             "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags"
                             "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-distributionconfig.html")
        if "OriginGroups" in distroConfig.keys():
            # not going to bounce a user for not specifying origin groups, but tbh they should use the native cfn AWS::CloudFront::Distribution rather than this custom resource
            # if not using origin groups
            if not isinstance(distroConfig["OriginGroups"], list):
                raise TypeError(f"'OriginGroups' is expected to be a list, got: {type(distroConfig['OriginGroups'])}")
            if not len(distroConfig["OriginGroups"]) > 0:
                raise ValueError("'OriginGroups' cannot be a zero length list")
            instantiate_args["OriginGroups"] = OriginGroups.from_cfn_form(originGroupsList=distroConfig["OriginGroups"])
        if "DefaultCacheBehavior" in distroConfig.keys():
            if not isinstance(distroConfig["DefaultCacheBehavior"], dict):
                raise TypeError(
                    f"'DefaultCacheBehavior' in distribution config must be of type dict. got: {type(distroConfig['DefaultCacheBehavior'])}")
            instantiate_args["DefaultCacheBehavior"] = DefaultCacheBehavior.from_cfn_form(
                distroConfig["DefaultCacheBehavior"])
        else:
            raise ValueError("distro config must contain 'DefaultCacheBehavior'. ref:"
                             "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudfront.html#CloudFront.Client.create_distribution_with_tags"
                             "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-cloudfront-distribution-distributionconfig.html")
        if "CacheBehaviors" in distroConfig.keys():
            if not isinstance(distroConfig["CacheBehaviors"], list):
                raise TypeError(
                    f"'CacheBehaviors' in distribution config must be of type list (of dict). got: {type(distroConfig['CacheBehaviors'])}")
            instantiate_args["CacheBehaviors"] = CacheBehaviors.from_cfn_form(distroConfig["CacheBehaviors"])
        else:
            instantiate_args["CacheBehaviors"] = CacheBehaviors(Quantity=0)
        if "CustomErrorResponses" in distroConfig.keys():
            if not isinstance(distroConfig["CustomErrorResponses"], list):
                raise TypeError(
                    f"'CustomErrorResponses' in distribution config must be of type list (of dict). got: {type(distroConfig['CustomErrorResponses'])}")
            instantiate_args["CustomErrorResponses"] = CustomErrorResponses.from_cfn_form(
                distroConfig["CustomErrorResponses"])
        else:
            instantiate_args["CustomErrorResponses"] = CustomErrorResponses(Quantity=0)
        if "Comment" in distroConfig.keys():
            if not isinstance(distroConfig["Comment"], str):
                raise TypeError(
                    f"'Comment' in 'DistributionConfig' must be of type string. got: {type(distroConfig['Comment'])}")
            instantiate_args["Comment"] = distroConfig["Comment"]
        else:
            instantiate_args["Comment"] = cls.Comment
        if "Logging" in distroConfig.keys():
            if not isinstance(distroConfig["Logging"], dict):
                raise TypeError(
                    f"'Logging' in 'DistributionConfig' must be of type dict. got: {type(distroConfig['Logging'])}")
            instantiate_args["Logging"] = Logging.from_cfn_form(distroConfig["Logging"])
        else:
            instantiate_args["Logging"] = Logging(Bucket="", Enabled=False, IncludeCookies=False, Prefix="")
        if "PriceClass" in distroConfig.keys():
            if not isinstance(distroConfig["PriceClass"], str):
                raise TypeError(
                    f"'PriceClass' in 'DistributionConfig' must be of type string. got: {type(distroConfig['PriceClass'])}")
            instantiate_args["PriceClass"] = distroConfig["PriceClass"]
        else:
            instantiate_args["PriceClass"] = cls.PriceClass
        if "ViewerCertificate" in distroConfig.keys():
            if not isinstance(distroConfig["ViewerCertificate"], dict):
                raise TypeError(
                    f"'ViewerCertificate' in 'DistributionConfig' must be of type dict. got: {type(distroConfig['ViewerCertificate'])}")
            instantiate_args["ViewerCertificate"] = ViewerCertificate.from_cfn_form(distroConfig["ViewerCertificate"])
        else:
            instantiate_args["ViewerCertificate"] = ViewerCertificate(CloudFrontDefaultCertificate=True)
        if "Restrictions" in distroConfig.keys():
            if not isinstance(distroConfig["Restrictions"], dict):
                raise TypeError(
                    f"'Restrictions' in 'DistributionConfig' must be of type dict. got: {type(distroConfig['Restrictions'])}")
            instantiate_args["Restrictions"] = Restrictions.from_cfn_form(distroConfig["Restrictions"])
        else:
            instantiate_args["Restrictions"] = Restrictions()
        if "WebACLId" in distroConfig.keys():
            if not isinstance(distroConfig["WebACLId"], str):
                raise TypeError(
                    f"'WebACLId' in 'DistributionConfig' must be of type string. got: {type(distroConfig['WebACLId'])}")
            instantiate_args["WebACLId"] = distroConfig["WebACLId"]
        else:
            instantiate_args["WebACLId"] = cls.WebACLId
        if "HttpVersion" in distroConfig.keys():
            if not isinstance(distroConfig["HttpVersion"], str):
                raise TypeError(
                    f"'HttpVersion' in 'DistributionConfig' must be of type string. got: {type(distroConfig['HttpVersion'])}")
            instantiate_args["HttpVersion"] = distroConfig["HttpVersion"]
        else:
            instantiate_args["HttpVersion"] = cls.HttpVersion
        if "IsIPV6Enabled" in distroConfig.keys():
            # cfn data types for params don't seem to include boolean - ref: https://github.com/awslabs/serverless-application-model/issues/501
            if isinstance(distroConfig["IsIPV6Enabled"], str):
                try:
                    isIPV6Enabled_bool = str2bool(distroConfig["IsIPV6Enabled"], raise_exc=True)
                except Exception as CastEx:
                    raise ValueError(
                        f"unable to cast string for 'DistributionConfig' 'IsIPV6Enabled' state to boolean. got: {distroConfig['IsIPV6Enabled']}"
                        f"{str(CastEx)}")
                instantiate_args["IsIPV6Enabled"] = isIPV6Enabled_bool
            elif isinstance(distroConfig["IsIPV6Enabled"], bool):
                instantiate_args["IsIPV6Enabled"] = distroConfig["IsIPV6Enabled"]
            else:
                raise TypeError(
                    f"'IsIPV6Enabled' in 'DistributionConfig' must be of type str (cast) or bool. got {type(distroConfig['IsIPV6Enabled'])}")
        else:
            instantiate_args["IsIPV6Enabled"] = cls.IsIPV6Enabled

        return DistributionConfig(**instantiate_args)

    def to_dict(self) -> dict:
        retval = {}
        retval["CallerReference"] = self.CallerReference
        retval["DefaultRootObject"] = self.DefaultRootObject

        if self.Aliases is not None:
            retval["Aliases"] = self.Aliases.to_dict()

        if self.Origins is None:
            raise AssertionError(f"invalid 'DistributionConfig' - 'Origins' cannot be NoneType")
        retval["Origins"] = self.Origins.to_dict()

        if self.OriginGroups is not None:
            retval["OriginGroups"] = self.OriginGroups.to_dict()

        if self.DefaultCacheBehavior is None:
            raise AssertionError(f"invalid 'DistributionConfig' - 'DefaultCacheBehavior' cannot be NoneType")
        retval["DefaultCacheBehavior"] = self.DefaultCacheBehavior.to_dict()

        if self.CacheBehaviors is not None:
            retval["CacheBehaviors"] = self.CacheBehaviors.to_dict()

        if self.CustomErrorResponses is not None:
            retval["CustomErrorResponses"] = self.CustomErrorResponses.to_dict()

        if self.Comment is None:
            raise AssertionError(
                f"invalid 'DistributionConfig' - 'Comment' cannot be NoneType - hint: put a blank string")
        retval["Comment"] = self.Comment

        if self.Logging is not None:
            retval["Logging"] = self.Logging.to_dict()

        retval["PriceClass"] = self.PriceClass

        if self.Enabled is None:
            raise AssertionError(f"invalid 'DistributionConfig' - 'Enabled' cannot be NoneType - hint: set bool value")
        retval["Enabled"] = self.Enabled

        if self.ViewerCertificate is not None:
            retval["ViewerCertificate"] = self.ViewerCertificate.to_dict()

        if self.Restrictions is not None:
            retval["Restrictions"] = self.Restrictions.to_dict()

        retval["WebACLId"] = self.WebACLId
        retval["HttpVersion"] = self.HttpVersion
        retval["IsIPV6Enabled"] = self.IsIPV6Enabled

        retval = trim_null_keys(retval)
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Tag:
    Key: str
    Value: str

    def to_dict(self):
        return {"Key": self.Key, "Value": self.Value}

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Tags:
    Items: Optional[List[Tag]]

    @classmethod
    def from_cfn_form(cls, tagList) -> 'Tags':
        if not isinstance(tagList, list):
            raise TypeError(f"'Tags' must be of type list (of dict). got: {type(tagList)}")

        return cls(Items=[Tag(i["Key"], i["Value"]) for i in tagList])

    def to_dict(self):
        retval = {"Items": [self.Items[i].to_dict() for i in range(len(self.Items))]}
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()


@dataclass
class Distribution:
    DistributionConfig: DistributionConfig
    Tags: Optional[Tags] = None

    @classmethod
    def from_cfn_form(cls, distributionConfigDict: dict, tagsList: list = None) -> 'Distribution':
        if not isinstance(distributionConfigDict, dict):
            raise TypeError(f"'DistributionConfig' must be of type dict. got: {type(distributionConfigDict)}")
        if tagsList is not None:
            if not isinstance(tagsList, list):
                raise TypeError(f"'Tags' must be of type list (of dict). got: {type(tagsList)}")
            return cls(DistributionConfig=DistributionConfig.from_cfn_form(distributionConfigDict),
                       Tags=Tags.from_cfn_form(tagsList))

        return cls(DistributionConfig=DistributionConfig.from_cfn_form(distributionConfigDict))

    def to_dict(self):
        retval = {"DistributionConfig": self.DistributionConfig.to_dict()}
        if self.Tags is not None:
            retval["Tags"] = self.Tags.to_dict()
        return retval

    def __eq__(self, other):
        return type(self) == type(other) and self.to_dict() == other.to_dict()

# TODO: tidy casting, de-dupe cachebehavior/defaultcachebehavior (default is pathpattern: '*')
