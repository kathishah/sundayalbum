"""CDK stack for Sunday Album Web UI — Phase 1 + Phase 2 + Phase 3."""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_dynamodb as dynamodb,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration, WebSocketLambdaIntegration
from constructs import Construct


class SundayAlbumStack(Stack):
    """All Sunday Album AWS resources in a single stack.

    Args:
        stage: Deployment stage — "prod" or "dev".
            prod: resource names use current conventions (no suffix); RETAIN policy.
            dev:  all resource names suffixed "-dev"; DESTROY policy for clean teardown.
    """

    def __init__(self, scope: Construct, construct_id: str, stage: str = "prod", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Stage-derived naming helpers
        # prod → suffix="" so existing prod resource names are unchanged
        # dev  → suffix="-dev"
        suffix = "" if stage == "prod" else f"-{stage}"
        removal_policy = RemovalPolicy.RETAIN if stage == "prod" else RemovalPolicy.DESTROY

        # ── S3 Bucket ────────────────────────────────────────────────────────
        bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=f"sundayalbum-data-{self.account}-{self.region}{suffix}",
            removal_policy=removal_policy,
            auto_delete_objects=(removal_policy == RemovalPolicy.DESTROY),
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-uploads",
                    prefix="uploads/",
                    expiration=Duration.days(30),
                ),
                s3.LifecycleRule(
                    id="expire-debug",
                    prefix="debug/",
                    expiration=Duration.days(7),
                ),
                s3.LifecycleRule(
                    id="expire-output",
                    prefix="output/",
                    expiration=Duration.days(30),
                ),
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.HEAD,
                    ],
                    allowed_origins=["*"],  # restrict in Phase 6
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
        )

        # ── DynamoDB Tables ──────────────────────────────────────────────────
        sessions_table = dynamodb.Table(
            self,
            "SessionsTable",
            table_name=f"sa-sessions{suffix}",
            partition_key=dynamodb.Attribute(
                name="email", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="token_expires_at",
            removal_policy=removal_policy,
        )
        sessions_table.add_global_secondary_index(
            index_name="token-index",
            partition_key=dynamodb.Attribute(
                name="session_token", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        jobs_table = dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"sa-jobs{suffix}",
            partition_key=dynamodb.Attribute(
                name="user_hash", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="job_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=removal_policy,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        ws_table = dynamodb.Table(
            self,
            "WsConnectionsTable",
            table_name=f"sa-ws-connections{suffix}",
            partition_key=dynamodb.Attribute(
                name="connection_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal_policy,
        )
        ws_table.add_global_secondary_index(
            index_name="job-index",
            partition_key=dynamodb.Attribute(
                name="job_id", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── User settings table (API keys, encrypted at rest) ────────────────
        user_settings_table = dynamodb.Table(
            self,
            "UserSettingsTable",
            table_name=f"sa-user-settings{suffix}",
            partition_key=dynamodb.Attribute(
                name="user_hash", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=removal_policy,
        )

        # ── Secrets Manager: system API keys ─────────────────────────────────
        # Secret value populated post-deploy via CLI (see migration steps).
        # Lambdas fetch at cold start and cache; never exposed in env vars.
        api_keys_secret = secretsmanager.Secret(
            self,
            "ApiKeysSecret",
            secret_name=f"sundayalbum/api-keys{suffix}",
            description=f"System Anthropic + OpenAI API keys ({stage})",
            removal_policy=removal_policy,
        )

        # ── Shared Lambda execution role ─────────────────────────────────────
        ses_sender = (
            self.node.try_get_context("ses_sender_email") or "noreply@sundayalbum.com"
        )

        lambda_role = iam.Role(
            self,
            "ApiLambdaRole",
            role_name=f"sa-api-lambda-role{suffix}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        sessions_table.grant_read_write_data(lambda_role)
        jobs_table.grant_read_write_data(lambda_role)
        ws_table.grant_read_write_data(lambda_role)
        user_settings_table.grant_read_write_data(lambda_role)
        bucket.grant_read_write(lambda_role)
        api_keys_secret.grant_read(lambda_role)

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="SesEmailSend",
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="StepFunctionsStart",
                actions=["states:StartExecution", "states:DescribeExecution"],
                resources=["*"],
            )
        )

        # ── Shared environment variables ─────────────────────────────────────
        # ADMIN_EMAILS: comma-separated list of emails exempt from rate limits.
        # Adding new admins requires a CDK redeploy (deliberate — not a hot config).
        admin_emails = self.node.try_get_context("admin_emails") or "kathi.shah@gmail.com,chintan@reachto.me"

        common_env = {
            "SESSIONS_TABLE": sessions_table.table_name,
            "JOBS_TABLE": jobs_table.table_name,
            "WS_CONNECTIONS_TABLE": ws_table.table_name,
            "USER_SETTINGS_TABLE": user_settings_table.table_name,
            "S3_BUCKET": bucket.bucket_name,
            "SES_SENDER": ses_sender,
            "AWS_ACCOUNT_ID": self.account,
            "AWS_DEPLOY_REGION": self.region,
            "ADMIN_EMAILS": admin_emails,
            "SECRET_ARN": api_keys_secret.secret_arn,
        }

        # ── API Lambda functions (zip-based) ─────────────────────────────────
        lambda_code = lambda_.Code.from_asset("../api")
        py312 = lambda_.Runtime.PYTHON_3_12

        auth_fn = lambda_.Function(
            self,
            "AuthFunction",
            function_name=f"sa-auth{suffix}",
            runtime=py312,
            handler="auth.handler",
            code=lambda_code,
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(30),
            memory_size=512,
            description=f"Sunday Album auth ({stage}): send-code, verify, logout",
        )

        jobs_fn = lambda_.Function(
            self,
            "JobsFunction",
            function_name=f"sa-jobs{suffix}",
            runtime=py312,
            handler="jobs.handler",
            code=lambda_code,
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(30),
            memory_size=512,
            description=f"Sunday Album jobs ({stage}): CRUD, presigned URLs, pipeline trigger",
        )

        ws_fn = lambda_.Function(
            self,
            "WebSocketFunction",
            function_name=f"sa-websocket{suffix}",
            runtime=py312,
            handler="websocket.handler",
            code=lambda_code,
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(29),
            memory_size=256,
            description=f"Sunday Album WebSocket ({stage}): connect, disconnect, broadcast",
        )

        # ── Pipeline Lambda functions (container image) ───────────────────────
        pipeline_env = {
            "JOBS_TABLE": jobs_table.table_name,
            "S3_BUCKET": bucket.bucket_name,
            "AWS_DEPLOY_REGION": self.region,
            "SECRET_ARN": api_keys_secret.secret_arn,
        }

        def pipeline_fn(
            construct_id: str,
            fn_base: str,
            handler: str,
            timeout_secs: int = 300,
            memory_mb: int = 1024,
            description: str = "",
        ) -> lambda_.DockerImageFunction:
            return lambda_.DockerImageFunction(
                self,
                construct_id,
                function_name=f"{fn_base}{suffix}",
                code=lambda_.DockerImageCode.from_image_asset(
                    "../",
                    cmd=[handler],
                    platform=ecr_assets.Platform.LINUX_ARM64,
                ),
                role=lambda_role,
                environment=pipeline_env,
                timeout=Duration.seconds(timeout_secs),
                memory_size=memory_mb,
                architecture=lambda_.Architecture.ARM_64,
                description=f"{description or fn_base} ({stage})",
            )

        load_fn        = pipeline_fn("LoadFunction",        "sa-pipeline-load",         "handlers.load.handler",         timeout_secs=60,  memory_mb=3008, description="Load & decode source image")
        normalize_fn   = pipeline_fn("NormalizeFunction",   "sa-pipeline-normalize",    "handlers.normalize.handler",    timeout_secs=60,  memory_mb=3008, description="Resize & orient image")
        page_detect_fn = pipeline_fn("PageDetectFunction",  "sa-pipeline-page-detect",  "handlers.page_detect.handler",  timeout_secs=120, memory_mb=3008, description="Detect album page boundary")
        perspective_fn = pipeline_fn("PerspectiveFunction", "sa-pipeline-perspective",  "handlers.perspective.handler",  timeout_secs=120, memory_mb=3008, description="Perspective / keystone correction")
        photo_detect_fn= pipeline_fn("PhotoDetectFunction", "sa-pipeline-photo-detect", "handlers.photo_detect.handler", timeout_secs=120, memory_mb=3008, description="Detect individual photo boundaries")
        photo_split_fn = pipeline_fn("PhotoSplitFunction",  "sa-pipeline-photo-split",  "handlers.photo_split.handler",  timeout_secs=120, memory_mb=3008, description="Extract individual photo crops")
        ai_orient_fn   = pipeline_fn("AiOrientFunction",    "sa-pipeline-ai-orient",    "handlers.ai_orient.handler",    timeout_secs=60,  memory_mb=1024, description="AI orientation correction (Claude Haiku)")
        glare_remove_fn= pipeline_fn("GlareRemoveFunction", "sa-pipeline-glare-remove", "handlers.glare_remove.handler", timeout_secs=300, memory_mb=3008, description="Glare removal (OpenAI gpt-image-1.5)")
        geometry_fn    = pipeline_fn("GeometryFunction",    "sa-pipeline-geometry",     "handlers.geometry.handler",     timeout_secs=120, memory_mb=3008, description="Geometry correction")
        color_restore_fn=pipeline_fn("ColorRestoreFunction","sa-pipeline-color-restore","handlers.color_restore.handler",timeout_secs=120, memory_mb=3008, description="Color restoration")
        finalize_fn    = pipeline_fn("FinalizeFunction",    "sa-pipeline-finalize",     "handlers.finalize.handler",     timeout_secs=60,  memory_mb=512,  description="Collect results, mark job complete")

        # ── Step Functions State Machine ─────────────────────────────────────
        # output_path="$.Payload" unwraps the Lambda response wrapper so each
        # handler receives the flat event dict, not {"Payload": {...}}.
        def invoke(task_id: str, fn: lambda_.IFunction, comment: str = "") -> sfn_tasks.LambdaInvoke:
            return sfn_tasks.LambdaInvoke(
                self,
                task_id,
                lambda_function=fn,
                payload=sfn.TaskInput.from_json_path_at("$"),
                output_path="$.Payload",
                comment=comment or task_id,
            )

        # ── Task states (no transitions set here) ─────────────────────────────
        load_task         = invoke("Load",         load_fn,          "Decode source image from S3")
        normalize_task    = invoke("Normalize",    normalize_fn,     "Resize & fix orientation")
        page_detect_task  = invoke("PageDetect",   page_detect_fn,   "Detect album page boundary")
        perspective_task  = invoke("Perspective",  perspective_fn,   "Apply perspective correction")
        photo_detect_task = invoke("PhotoDetect",  photo_detect_fn,  "Detect individual photo regions")
        photo_split_task  = invoke("PhotoSplit",   photo_split_fn,   "Extract individual photo crops")
        ai_orient_task    = invoke("AiOrient",     ai_orient_fn,     "AI orientation correction")
        glare_remove_task = invoke("GlareRemove",  glare_remove_fn,  "Glare removal")
        geometry_task     = invoke("Geometry",     geometry_fn,      "Geometry correction")
        color_restore_task= invoke("ColorRestore", color_restore_fn, "Color restoration")
        finalize_task     = invoke("Finalize",     finalize_fn,      "Collect results, mark job complete")

        # ── Pass (skipped) states — one per guarded step ──────────────────────
        load_skipped         = sfn.Pass(self, "LoadSkipped",        comment="Load skipped — reprocessing from later step")
        normalize_skipped    = sfn.Pass(self, "NormalizeSkipped",   comment="Normalize skipped — reprocessing from later step")
        page_detect_skipped  = sfn.Pass(self, "PageDetectSkipped",  comment="PageDetect skipped — reprocessing from later step")
        perspective_skipped  = sfn.Pass(self, "PerspectiveSkipped", comment="Perspective skipped — reprocessing from later step")
        photo_detect_skipped = sfn.Pass(self, "PhotoDetectSkipped", comment="PhotoDetect skipped — reprocessing from later step")
        photo_split_skipped  = sfn.Pass(self, "PhotoSplitSkipped",  comment="PhotoSplit skipped — reprocessing from later step")
        ai_orient_skipped    = sfn.Pass(self, "AiOrientSkipped",    comment="AiOrient skipped — reprocessing from later step")
        glare_remove_skipped = sfn.Pass(self, "GlareRemoveSkipped", comment="GlareRemove skipped — reprocessing from later step")
        geometry_skipped     = sfn.Pass(self, "GeometrySkipped",    comment="Geometry skipped — reprocessing from later step")

        # ── PrepareMap Pass — builds photo_indices array for the Map state ────
        prepare_map = sfn.Pass(
            self,
            "PrepareMap",
            comment="Generate photo index array for Map state",
            parameters={
                "user_hash.$":              "$.user_hash",
                "job_id.$":                 "$.job_id",
                "stem.$":                   "$.stem",
                "start_time.$":             "$.start_time",
                "photo_count.$":            "$.photo_count",
                "config.$":                 "$.config",
                "user_keys.$":              "$.user_keys",
                "start_from.$":             "$.start_from",
                "reprocess_photo_index.$":  "$.reprocess_photo_index",
                "photo_indices.$":          "States.ArrayRange(1, $.photo_count, 1)",
            },
        )

        # ── Helper: build OR condition from a list of step name strings ───────
        def skip_when(*steps: str) -> sfn.Condition:
            conditions = [sfn.Condition.string_equals("$.start_from", s) for s in steps]
            return sfn.Condition.or_(*conditions) if len(conditions) > 1 else conditions[0]

        # ── Per-photo chain (inside Map iterator), wired from end → front ─────
        # ColorRestore is terminal (no guard — it's last).
        # Each skipped Pass and its corresponding Task both point to the same
        # next guard Choice, so the event flows through regardless of branch.

        geometry_skipped.next(color_restore_task)
        geometry_task.next(color_restore_task)
        skip_geometry = (
            sfn.Choice(self, "SkipGeometry?", comment="Skip Geometry if reprocessing from color_restore")
            .when(skip_when("color_restore"), geometry_skipped)
            .otherwise(geometry_task)
        )

        glare_remove_skipped.next(skip_geometry)
        glare_remove_task.next(skip_geometry)
        skip_glare_remove = (
            sfn.Choice(self, "SkipGlareRemove?", comment="Skip GlareRemove if reprocessing from geometry or later")
            .when(skip_when("geometry", "color_restore"), glare_remove_skipped)
            .otherwise(glare_remove_task)
        )

        ai_orient_skipped.next(skip_glare_remove)
        ai_orient_task.next(skip_glare_remove)
        skip_ai_orient = (
            sfn.Choice(self, "SkipAiOrient?", comment="Skip AiOrient if reprocessing from glare_remove or later")
            .when(skip_when("glare_remove", "geometry", "color_restore"), ai_orient_skipped)
            .otherwise(ai_orient_task)
        )

        # ── Map state (processes each photo in parallel) ──────────────────────
        process_photos_map = sfn.Map(
            self,
            "ProcessPhotos",
            comment="Process each photo in parallel (AI orient → glare → geometry → color)",
            items_path="$.photo_indices",
            item_selector={
                "photo_index.$":            "$$.Map.Item.Value",
                "user_hash.$":              "$.user_hash",
                "job_id.$":                 "$.job_id",
                "stem.$":                   "$.stem",
                "start_time.$":             "$.start_time",
                "config.$":                 "$.config",
                "user_keys.$":              "$.user_keys",
                "start_from.$":             "$.start_from",
                "reprocess_photo_index.$":  "$.reprocess_photo_index",
            },
            max_concurrency=4,
            result_path="$.photo_results",
        )
        process_photos_map.item_processor(sfn.Chain.start(skip_ai_orient))
        process_photos_map.next(finalize_task)

        # ── Pre-split chain, wired from end → front ───────────────────────────
        prepare_map.next(process_photos_map)

        photo_split_skipped.next(prepare_map)
        photo_split_task.next(prepare_map)
        skip_photo_split = (
            sfn.Choice(self, "SkipPhotoSplit?", comment="Skip PhotoSplit if reprocessing from per-photo step")
            .when(skip_when("ai_orient", "glare_remove", "geometry", "color_restore"), photo_split_skipped)
            .otherwise(photo_split_task)
        )

        photo_detect_skipped.next(skip_photo_split)
        photo_detect_task.next(skip_photo_split)
        skip_photo_detect = (
            sfn.Choice(self, "SkipPhotoDetect?", comment="Skip PhotoDetect if reprocessing from photo_split or later")
            .when(skip_when("photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"), photo_detect_skipped)
            .otherwise(photo_detect_task)
        )

        perspective_skipped.next(skip_photo_detect)
        perspective_task.next(skip_photo_detect)
        skip_perspective = (
            sfn.Choice(self, "SkipPerspective?", comment="Skip Perspective if reprocessing from photo_detect or later")
            .when(skip_when("photo_detect", "photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"), perspective_skipped)
            .otherwise(perspective_task)
        )

        page_detect_skipped.next(skip_perspective)
        page_detect_task.next(skip_perspective)
        skip_page_detect = (
            sfn.Choice(self, "SkipPageDetect?", comment="Skip PageDetect if reprocessing from perspective or later")
            .when(skip_when("perspective", "photo_detect", "photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"), page_detect_skipped)
            .otherwise(page_detect_task)
        )

        normalize_skipped.next(skip_page_detect)
        normalize_task.next(skip_page_detect)
        skip_normalize = (
            sfn.Choice(self, "SkipNormalize?", comment="Skip Normalize if reprocessing from page_detect or later")
            .when(skip_when("page_detect", "perspective", "photo_detect", "photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"), normalize_skipped)
            .otherwise(normalize_task)
        )

        load_skipped.next(skip_normalize)
        load_task.next(skip_normalize)
        skip_load = (
            sfn.Choice(self, "SkipLoad?", comment="Skip Load if reprocessing from normalize or later")
            .when(skip_when("normalize", "page_detect", "perspective", "photo_detect", "photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"), load_skipped)
            .otherwise(load_task)
        )

        definition = sfn.Chain.start(skip_load)

        sfn_role = iam.Role(
            self,
            "StateMachineRole",
            role_name=f"sa-state-machine-role{suffix}",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaRole"
                )
            ],
        )
        for fn in [
            load_fn, normalize_fn, page_detect_fn, perspective_fn,
            photo_detect_fn, photo_split_fn, ai_orient_fn, glare_remove_fn,
            geometry_fn, color_restore_fn, finalize_fn,
        ]:
            fn.grant_invoke(sfn_role)

        state_machine = sfn.StateMachine(
            self,
            "PipelineStateMachine",
            state_machine_name=f"sa-pipeline{suffix}",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            role=sfn_role,
            timeout=Duration.minutes(30),
            comment=f"Sunday Album photo processing pipeline ({stage})",
        )

        jobs_fn.add_environment("STATE_MACHINE_ARN", state_machine.state_machine_arn)

        settings_fn = lambda_.Function(
            self,
            "SettingsFunction",
            function_name=f"sa-settings{suffix}",
            runtime=py312,
            handler="settings.handler",
            code=lambda_code,
            role=lambda_role,
            environment=common_env,
            timeout=Duration.seconds(30),
            memory_size=512,
            description=f"Sunday Album settings ({stage}): user API key management",
        )

        broadcaster_fn = lambda_.Function(
            self,
            "BroadcasterFunction",
            function_name=f"sa-broadcaster{suffix}",
            runtime=py312,
            handler="broadcaster.handler",
            code=lambda_code,
            role=lambda_role,
            environment=common_env,  # WS_ENDPOINT added post-creation below
            timeout=Duration.seconds(30),
            memory_size=256,
            description=f"Sunday Album broadcaster ({stage}): DDB Streams → WebSocket push",
        )

        # DynamoDB Streams trigger: sa-jobs → broadcaster
        broadcaster_fn.add_event_source(
            event_sources.DynamoEventSource(
                jobs_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_error=True,
                retry_attempts=2,
            )
        )

        # ── API Gateway HTTP API ─────────────────────────────────────────────
        http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"sundayalbum-api{suffix}",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],  # restrict in Phase 6
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_headers=["Content-Type", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )

        auth_int = HttpLambdaIntegration("AuthSendCode", auth_fn)
        http_api.add_routes(path="/auth/send-code", methods=[apigw.HttpMethod.POST], integration=auth_int)
        http_api.add_routes(path="/auth/verify",    methods=[apigw.HttpMethod.POST], integration=HttpLambdaIntegration("AuthVerify",  auth_fn))
        http_api.add_routes(path="/auth/logout",    methods=[apigw.HttpMethod.POST], integration=HttpLambdaIntegration("AuthLogout",  auth_fn))

        http_api.add_routes(path="/jobs",               methods=[apigw.HttpMethod.GET],    integration=HttpLambdaIntegration("JobsList",      jobs_fn))
        http_api.add_routes(path="/jobs",               methods=[apigw.HttpMethod.POST],   integration=HttpLambdaIntegration("JobsCreate",    jobs_fn))
        http_api.add_routes(path="/jobs/{jobId}",       methods=[apigw.HttpMethod.GET],    integration=HttpLambdaIntegration("JobsGet",       jobs_fn))
        http_api.add_routes(path="/jobs/{jobId}",       methods=[apigw.HttpMethod.DELETE], integration=HttpLambdaIntegration("JobsDelete",    jobs_fn))
        http_api.add_routes(path="/jobs/{jobId}/start",     methods=[apigw.HttpMethod.POST], integration=HttpLambdaIntegration("JobsStart",     jobs_fn))
        http_api.add_routes(path="/jobs/{jobId}/reprocess", methods=[apigw.HttpMethod.POST], integration=HttpLambdaIntegration("JobsReprocess", jobs_fn))

        settings_int = HttpLambdaIntegration("SettingsApiKeys", settings_fn)
        http_api.add_routes(path="/settings/api-keys", methods=[apigw.HttpMethod.GET],    integration=settings_int)
        http_api.add_routes(path="/settings/api-keys", methods=[apigw.HttpMethod.PUT],    integration=HttpLambdaIntegration("SettingsApiKeysPut",    settings_fn))
        http_api.add_routes(path="/settings/api-keys", methods=[apigw.HttpMethod.DELETE], integration=HttpLambdaIntegration("SettingsApiKeysDelete", settings_fn))

        # ── API Gateway WebSocket API ─────────────────────────────────────────
        ws_api = apigw.WebSocketApi(
            self,
            "WebSocketApi",
            api_name=f"sundayalbum-ws{suffix}",
            connect_route_options=apigw.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration("WsConnect", ws_fn),
            ),
            disconnect_route_options=apigw.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration("WsDisconnect", ws_fn),
            ),
            default_route_options=apigw.WebSocketRouteOptions(
                integration=WebSocketLambdaIntegration("WsDefault", ws_fn),
            ),
        )

        ws_stage = apigw.WebSocketStage(
            self,
            "WebSocketStage",
            web_socket_api=ws_api,
            stage_name="$default",
            auto_deploy=True,
        )

        # Management endpoint for posting to connections (https, not wss)
        ws_mgmt_endpoint = (
            f"https://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/$default"
        )

        # Inject WS_ENDPOINT into ws_fn and broadcaster_fn after ws_api exists
        ws_fn.add_environment("WS_ENDPOINT", ws_mgmt_endpoint)
        broadcaster_fn.add_environment("WS_ENDPOINT", ws_mgmt_endpoint)

        # Grant ManageConnections so both Lambdas can push to WebSocket clients
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                sid="WebSocketManageConnections",
                actions=["execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{self.region}:{self.account}:{ws_api.api_id}/*"
                ],
            )
        )

        # ── Outputs ──────────────────────────────────────────────────────────
        # Export names are stage-suffixed so both stacks can coexist in the same account.
        CfnOutput(self, "ApiUrl",                value=http_api.api_endpoint,               export_name=f"SundayAlbumApiUrl-{stage}",               description=f"HTTP API base URL ({stage})")
        CfnOutput(self, "WebSocketUrl",          value=ws_stage.url,                        export_name=f"SundayAlbumWebSocketUrl-{stage}",          description=f"WebSocket URL (wss://) for clients ({stage})")
        CfnOutput(self, "BucketName",            value=bucket.bucket_name,                  export_name=f"SundayAlbumBucketName-{stage}",            description=f"S3 data bucket ({stage})")
        CfnOutput(self, "SessionsTableName",     value=sessions_table.table_name,           export_name=f"SundayAlbumSessionsTable-{stage}")
        CfnOutput(self, "JobsTableName",         value=jobs_table.table_name,               export_name=f"SundayAlbumJobsTable-{stage}")
        CfnOutput(self, "UserSettingsTableName", value=user_settings_table.table_name,      export_name=f"SundayAlbumUserSettingsTable-{stage}")
        CfnOutput(self, "StateMachineArn",       value=state_machine.state_machine_arn,     export_name=f"SundayAlbumStateMachineArn-{stage}",      description=f"Step Functions state machine ARN ({stage})")
        CfnOutput(self, "AuthFunctionName",      value=auth_fn.function_name,               export_name=f"SundayAlbumAuthFunction-{stage}")
        CfnOutput(self, "JobsFunctionName",      value=jobs_fn.function_name,               export_name=f"SundayAlbumJobsFunction-{stage}")
        CfnOutput(self, "ApiKeysSecretArn",      value=api_keys_secret.secret_arn,          export_name=f"SundayAlbumApiKeysSecret-{stage}")

        # Resource references for cross-stack use in later phases
        self.stage = stage
        self.bucket = bucket
        self.sessions_table = sessions_table
        self.jobs_table = jobs_table
        self.ws_table = ws_table
        self.user_settings_table = user_settings_table
        self.api_keys_secret = api_keys_secret
        self.http_api = http_api
        self.auth_fn = auth_fn
        self.jobs_fn = jobs_fn
        self.ws_fn = ws_fn
        self.settings_fn = settings_fn
        self.broadcaster_fn = broadcaster_fn
        self.ws_api = ws_api
        self.ws_stage = ws_stage
        self.state_machine = state_machine
