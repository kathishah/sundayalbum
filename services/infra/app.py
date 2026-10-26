#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.sundayalbum_stack import SundayAlbumStack

app = cdk.App()

stage = app.node.try_get_context("stage") or "prod"

# Prod keeps the original stack name to avoid replacing live resources.
# Dev gets a suffixed name so both stacks can coexist.
stack_name = "SundayAlbumStack" if stage == "prod" else f"SundayAlbumStack-{stage}"

SundayAlbumStack(
    app,
    stack_name,
    stage=stage,
    # The AWS CDK CLI sets CDK_DEFAULT_ACCOUNT from the credentials/profile in use, so the
    # account ID is not stored in the repo. Deploy with the profile for the target account.
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region="us-west-2"),
)
app.synth()
