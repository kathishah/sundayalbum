#!/usr/bin/env python3
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
    env=cdk.Environment(account="680073251743", region="us-west-2"),
)
app.synth()
