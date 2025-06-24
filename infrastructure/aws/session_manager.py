"""AWS session manager"""

import os
import boto3
from typing import Optional, Dict
from datetime import datetime
from core.utils.logger import get_infrastructure_logger


class AWSSessionManager:
    """Manages AWS sessions and cross-account role assumptions."""

    def __init__(self, region: str = "ap-southeast-2"):
        self.region = region
        self.logger = get_infrastructure_logger(__name__)

    @staticmethod
    def assume_role(
        account_id: str,
        account_name: str,
        role: str,
        region: str = "ap-southeast-2",
        role_session_name: str = "cms",
    ) -> boto3.Session:
        """Assumes a specified role in an AWS account and returns a boto3 Session."""
        role_arn = f"arn:aws:iam::{account_id}:role/{role}"
        if not account_id.isdigit() or len(account_id) != 12:
            raise ValueError("Invalid AWS account ID")
        try:
            sts_client = boto3.client("sts", region_name=region)
            credentials = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName=f"{account_name}-{role_session_name}"
            )["Credentials"]

            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=region,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to assume role {role_arn}: {e}")

    def get_session(
        self,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        session_duration: int = 3600,
        run_mode: str = "local",
    ) -> boto3.Session:
        """Get an AWS session for different execution modes."""
        # Mode 2: Pipeline execution - use environment variables
        if run_mode == "pipeline":
            self.logger.info("Using pipeline mode with environment credentials")
            return self.get_session_from_env(region=self.region)

        # Mode 1: Local execution - assume role from hub role
        if run_mode == "local":
            if not account_id or not role_name:
                self.logger.warning(
                    "No account_id or role_name provided, using default session"
                )
                return boto3.Session(region_name=self.region)

            return self._assume_role_session(account_id, role_name, session_duration)

        # Fallback for unknown modes
        raise ValueError(f"Unsupported run_mode: {run_mode}. Use 'local' or 'pipeline'")

    def _assume_role_session(
        self, account_id: str, role_name: str, session_duration: int = 3600
    ) -> boto3.Session:
        """Assume a cross-account role and return session."""
        try:
            # Construct role ARN
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

            # Create STS client from current session (hub role)
            sts_client = boto3.client("sts", region_name=self.region)

            # Assume the target role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=f"patching-session-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                DurationSeconds=session_duration,
            )

            credentials = response["Credentials"]

            # Create session with assumed role credentials
            assumed_session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=self.region,
            )

            self.logger.info(f"Successfully assumed role {role_arn}")
            return assumed_session

        except Exception as e:
            self.logger.error(f"Failed to assume role {role_arn}: {str(e)}")
            raise RuntimeError(f"Role assumption failed: {str(e)}") from e

    @classmethod
    def get_session_from_env(
        cls, region: str = "ap-southeast-2", session_name: str = "pipeline"
    ) -> boto3.Session:
        """Create a boto3 Session from environment variables for pipeline usage.

        Expected environment variables:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_SESSION_TOKEN
        """
        session_key = f"env:{region}:{session_name}"

        if session_key not in cls._sessions:
            # Check for AWS credentials in environment variables
            access_key = os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            session_token = os.getenv("AWS_SESSION_TOKEN")

            if not access_key or not secret_key:
                raise ValueError(
                    "Missing required environment variables. "
                    "Please set AWS_ACCESS_KEY_ID/AWS_ACCESS_KEY and AWS_SECRET_ACCESS_KEY/AWS_SECRET_KEY"
                )

            cls._sessions[session_key] = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=region,
            )

        return cls._sessions[session_key]
