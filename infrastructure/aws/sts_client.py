"""AWS STS client for identity and role management operations."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from botocore.exceptions import ClientError
from .session_manager import AWSSessionManager


class STSClient:
    """AWS STS client wrapper for identity and role operations."""
    
    def __init__(
        self,
        region: str = 'us-east-1',
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None
    ):
        self.region = region
        self.account_id = account_id
        self.role_name = role_name
        self.external_id = external_id
        self.logger = logging.getLogger(__name__)
        
        # Initialize session manager
        self.session_manager = AWSSessionManager(region=region)
        
        # Get STS client
        self._client = self.session_manager.get_client(
            'sts',
            account_id=account_id,
            role_name=role_name,
            external_id=external_id
        )
    
    async def get_caller_identity(self) -> Dict[str, Any]:
        """Get the current caller identity."""
        try:
            self.logger.debug("Getting caller identity")
            response = self._client.get_caller_identity()
            
            identity = {
                'user_id': response.get('UserId'),
                'account': response.get('Account'),
                'arn': response.get('Arn'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Caller identity: {identity['arn']} in account {identity['account']}")
            return identity
            
        except ClientError as e:
            self.logger.error(f"Failed to get caller identity: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting caller identity: {str(e)}")
            raise
    
    async def assume_role(
        self,
        role_arn: str,
        session_name: str,
        duration_seconds: int = 3600,
        external_id: Optional[str] = None,
        policy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assume an IAM role and return credentials."""
        try:
            self.logger.info(f"Assuming role: {role_arn}")
            
            # Prepare assume role parameters
            params = {
                'RoleArn': role_arn,
                'RoleSessionName': session_name,
                'DurationSeconds': duration_seconds
            }
            
            if external_id:
                params['ExternalId'] = external_id
            
            if policy:
                params['Policy'] = policy
            
            # Assume the role
            response = self._client.assume_role(**params)
            
            # Extract credentials
            credentials = response['Credentials']
            assumed_role_user = response['AssumedRoleUser']
            
            result = {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat(),
                'assumed_role_id': assumed_role_user['AssumedRoleId'],
                'assumed_role_arn': assumed_role_user['Arn']
            }
            
            self.logger.info(f"Successfully assumed role: {result['assumed_role_arn']}")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'AccessDenied':
                self.logger.error(f"Access denied assuming role {role_arn}: {error_message}")
            elif error_code == 'InvalidParameterValue':
                self.logger.error(f"Invalid parameter for role {role_arn}: {error_message}")
            else:
                self.logger.error(f"Error assuming role {role_arn}: {error_code} - {error_message}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error assuming role {role_arn}: {str(e)}")
            raise
    
    async def assume_role_with_saml(
        self,
        role_arn: str,
        principal_arn: str,
        saml_assertion: str,
        duration_seconds: int = 3600
    ) -> Dict[str, Any]:
        """Assume role with SAML assertion."""
        try:
            self.logger.info(f"Assuming role with SAML: {role_arn}")
            
            response = self._client.assume_role_with_saml(
                RoleArn=role_arn,
                PrincipalArn=principal_arn,
                SAMLAssertion=saml_assertion,
                DurationSeconds=duration_seconds
            )
            
            credentials = response['Credentials']
            assumed_role_user = response['AssumedRoleUser']
            
            result = {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat(),
                'assumed_role_id': assumed_role_user['AssumedRoleId'],
                'assumed_role_arn': assumed_role_user['Arn'],
                'subject': response.get('Subject'),
                'subject_type': response.get('SubjectType'),
                'issuer': response.get('Issuer'),
                'audience': response.get('Audience')
            }
            
            self.logger.info(f"Successfully assumed role with SAML: {result['assumed_role_arn']}")
            return result
            
        except ClientError as e:
            self.logger.error(f"Failed to assume role with SAML: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error assuming role with SAML: {str(e)}")
            raise
    
    async def assume_role_with_web_identity(
        self,
        role_arn: str,
        session_name: str,
        web_identity_token: str,
        duration_seconds: int = 3600,
        provider_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assume role with web identity token."""
        try:
            self.logger.info(f"Assuming role with web identity: {role_arn}")
            
            params = {
                'RoleArn': role_arn,
                'RoleSessionName': session_name,
                'WebIdentityToken': web_identity_token,
                'DurationSeconds': duration_seconds
            }
            
            if provider_id:
                params['ProviderId'] = provider_id
            
            response = self._client.assume_role_with_web_identity(**params)
            
            credentials = response['Credentials']
            assumed_role_user = response['AssumedRoleUser']
            
            result = {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat(),
                'assumed_role_id': assumed_role_user['AssumedRoleId'],
                'assumed_role_arn': assumed_role_user['Arn'],
                'subject_from_web_identity_token': response.get('SubjectFromWebIdentityToken'),
                'audience': response.get('Audience'),
                'provider': response.get('Provider')
            }
            
            self.logger.info(f"Successfully assumed role with web identity: {result['assumed_role_arn']}")
            return result
            
        except ClientError as e:
            self.logger.error(f"Failed to assume role with web identity: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error assuming role with web identity: {str(e)}")
            raise
    
    async def get_session_token(
        self,
        duration_seconds: int = 3600,
        serial_number: Optional[str] = None,
        token_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a session token for temporary credentials."""
        try:
            self.logger.info("Getting session token")
            
            params = {
                'DurationSeconds': duration_seconds
            }
            
            # Add MFA parameters if provided
            if serial_number and token_code:
                params['SerialNumber'] = serial_number
                params['TokenCode'] = token_code
                self.logger.info(f"Using MFA device: {serial_number}")
            
            response = self._client.get_session_token(**params)
            
            credentials = response['Credentials']
            
            result = {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat()
            }
            
            self.logger.info("Successfully obtained session token")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'AccessDenied':
                self.logger.error("Access denied getting session token - check MFA requirements")
            elif error_code == 'InvalidParameterValue':
                self.logger.error("Invalid MFA token or serial number")
            else:
                self.logger.error(f"Error getting session token: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting session token: {str(e)}")
            raise
    
    async def get_federation_token(
        self,
        name: str,
        policy: str,
        duration_seconds: int = 3600
    ) -> Dict[str, Any]:
        """Get federation token for temporary access."""
        try:
            self.logger.info(f"Getting federation token for: {name}")
            
            response = self._client.get_federation_token(
                Name=name,
                Policy=policy,
                DurationSeconds=duration_seconds
            )
            
            credentials = response['Credentials']
            federated_user = response['FederatedUser']
            
            result = {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat(),
                'federated_user_id': federated_user['FederatedUserId'],
                'federated_user_arn': federated_user['Arn']
            }
            
            self.logger.info(f"Successfully obtained federation token: {result['federated_user_arn']}")
            return result
            
        except ClientError as e:
            self.logger.error(f"Failed to get federation token: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting federation token: {str(e)}")
            raise
    
    async def decode_authorization_message(self, encoded_message: str) -> Dict[str, Any]:
        """Decode an authorization failure message."""
        try:
            self.logger.info("Decoding authorization message")
            
            response = self._client.decode_authorization_message(
                EncodedMessage=encoded_message
            )
            
            decoded_message = response['DecodedMessage']
            
            self.logger.info("Successfully decoded authorization message")
            return {
                'decoded_message': decoded_message,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            self.logger.error(f"Failed to decode authorization message: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error decoding authorization message: {str(e)}")
            raise
    
    async def validate_credentials(self) -> bool:
        """Validate current credentials by calling get_caller_identity."""
        try:
            await self.get_caller_identity()
            return True
        except Exception as e:
            self.logger.warning(f"Credential validation failed: {str(e)}")
            return False
    
    def get_account_id(self) -> Optional[str]:
        """Get the current account ID."""
        try:
            response = self._client.get_caller_identity()
            return response.get('Account')
        except Exception as e:
            self.logger.error(f"Failed to get account ID: {str(e)}")
            return None
    
    def get_user_arn(self) -> Optional[str]:
        """Get the current user/role ARN."""
        try:
            response = self._client.get_caller_identity()
            return response.get('Arn')
        except Exception as e:
            self.logger.error(f"Failed to get user ARN: {str(e)}")
            return None