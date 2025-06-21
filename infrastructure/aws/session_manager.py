"""AWS session manager for handling cross-account access and role assumptions."""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config


class AWSSessionManager:
    """Manages AWS sessions and cross-account role assumptions."""
    
    def __init__(self, region: str = 'us-east-1', max_retries: int = 3):
        self.region = region
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
        # Cache for assumed role sessions
        self._session_cache: Dict[str, Dict[str, Any]] = {}
        
        # Default boto3 config
        self._boto_config = Config(
            region_name=region,
            retries={
                'max_attempts': max_retries,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        # Base session (current credentials)
        self._base_session = None
        self._initialize_base_session()
    
    def _initialize_base_session(self) -> None:
        """Initialize the base AWS session."""
        try:
            self._base_session = boto3.Session()
            
            # Test credentials
            sts_client = self._base_session.client('sts', config=self._boto_config)
            identity = sts_client.get_caller_identity()
            
            self.logger.info(f"AWS session initialized for account: {identity.get('Account')}")
            self.logger.info(f"Using ARN: {identity.get('Arn')}")
            
        except NoCredentialsError:
            self.logger.error("No AWS credentials found. Please configure your credentials.")
            raise
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS session: {str(e)}")
            raise
    
    def get_session(
        self,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None,
        session_duration: int = 3600
    ) -> boto3.Session:
        """Get an AWS session, optionally assuming a cross-account role."""
        
        # If no account_id or role_name, return base session
        if not account_id or not role_name:
            return self._base_session
        
        # Check cache for existing valid session
        cache_key = f"{account_id}:{role_name}:{external_id or 'none'}"
        
        if cache_key in self._session_cache:
            cached_session = self._session_cache[cache_key]
            
            # Check if session is still valid (with 5-minute buffer)
            if datetime.utcnow() < cached_session['expires_at'] - timedelta(minutes=5):
                self.logger.debug(f"Using cached session for {cache_key}")
                return cached_session['session']
            else:
                # Remove expired session
                del self._session_cache[cache_key]
                self.logger.debug(f"Cached session expired for {cache_key}")
        
        # Assume role and create new session
        try:
            assumed_session = self._assume_role(
                account_id=account_id,
                role_name=role_name,
                external_id=external_id,
                session_duration=session_duration
            )
            
            # Cache the session
            self._session_cache[cache_key] = {
                'session': assumed_session,
                'expires_at': datetime.utcnow() + timedelta(seconds=session_duration)
            }
            
            self.logger.info(f"Created new assumed role session for {account_id}:{role_name}")
            return assumed_session
            
        except Exception as e:
            self.logger.error(f"Failed to assume role {role_name} in account {account_id}: {str(e)}")
            raise
    
    def _assume_role(
        self,
        account_id: str,
        role_name: str,
        external_id: Optional[str] = None,
        session_duration: int = 3600
    ) -> boto3.Session:
        """Assume a cross-account role and return a session."""
        
        # Construct role ARN
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        
        # Create STS client
        sts_client = self._base_session.client('sts', config=self._boto_config)
        
        # Prepare assume role parameters
        assume_role_params = {
            'RoleArn': role_arn,
            'RoleSessionName': f"patching-session-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            'DurationSeconds': session_duration
        }
        
        # Add external ID if provided
        if external_id:
            assume_role_params['ExternalId'] = external_id
        
        try:
            # Assume the role
            response = sts_client.assume_role(**assume_role_params)
            credentials = response['Credentials']
            
            # Create session with assumed role credentials
            assumed_session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region
            )
            
            # Verify the assumed session
            test_sts = assumed_session.client('sts', config=self._boto_config)
            identity = test_sts.get_caller_identity()
            
            self.logger.info(f"Successfully assumed role: {identity.get('Arn')}")
            
            return assumed_session
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            if error_code == 'AccessDenied':
                self.logger.error(f"Access denied when assuming role {role_arn}. Check permissions and trust policy.")
            elif error_code == 'InvalidUserID.NotFound':
                self.logger.error(f"Role {role_arn} not found. Check account ID and role name.")
            else:
                self.logger.error(f"Error assuming role {role_arn}: {error_code} - {error_message}")
            
            raise
    
    def get_client(
        self,
        service_name: str,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None,
        region: Optional[str] = None
    ):
        """Get an AWS service client, optionally with assumed role."""
        
        # Get appropriate session
        session = self.get_session(
            account_id=account_id,
            role_name=role_name,
            external_id=external_id
        )
        
        # Use provided region or default
        client_region = region or self.region
        
        # Create client with custom config
        config = Config(
            region_name=client_region,
            retries={
                'max_attempts': self.max_retries,
                'mode': 'adaptive'
            },
            max_pool_connections=50
        )
        
        return session.client(service_name, config=config)
    
    def get_resource(
        self,
        service_name: str,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None,
        region: Optional[str] = None
    ):
        """Get an AWS service resource, optionally with assumed role."""
        
        # Get appropriate session
        session = self.get_session(
            account_id=account_id,
            role_name=role_name,
            external_id=external_id
        )
        
        # Use provided region or default
        resource_region = region or self.region
        
        return session.resource(service_name, region_name=resource_region)
    
    def clear_session_cache(self) -> None:
        """Clear all cached sessions."""
        self._session_cache.clear()
        self.logger.info("Session cache cleared")
    
    def get_current_identity(self) -> Dict[str, Any]:
        """Get the current AWS identity information."""
        try:
            sts_client = self._base_session.client('sts', config=self._boto_config)
            return sts_client.get_caller_identity()
        except Exception as e:
            self.logger.error(f"Failed to get current identity: {str(e)}")
            raise
    
    def validate_role_access(
        self,
        account_id: str,
        role_name: str,
        external_id: Optional[str] = None
    ) -> bool:
        """Validate if the current credentials can assume the specified role."""
        try:
            # Try to assume the role with minimal duration
            session = self.get_session(
                account_id=account_id,
                role_name=role_name,
                external_id=external_id,
                session_duration=900  # 15 minutes minimum
            )
            
            # Test the session by getting caller identity
            sts_client = session.client('sts', config=self._boto_config)
            identity = sts_client.get_caller_identity()
            
            self.logger.info(f"Role access validated for {account_id}:{role_name}")
            self.logger.debug(f"Assumed identity: {identity.get('Arn')}")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Role access validation failed for {account_id}:{role_name}: {str(e)}")
            return False
    
    def get_available_regions(self, service_name: str = 'ec2') -> list:
        """Get list of available regions for a service."""
        try:
            session = self._base_session
            return session.get_available_regions(service_name)
        except Exception as e:
            self.logger.error(f"Failed to get available regions: {str(e)}")
            return []
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clear cache."""
        self.clear_session_cache()