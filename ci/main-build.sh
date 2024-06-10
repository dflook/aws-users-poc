#!/usr/bin/env bash

echo "Building for the main branch"

aws cloudformation create-change-set --stack-name Roles --change-set-name $(echo $CODEBUILD_WEBHOOK_TRIGGER | tr '/' '-')-$CODEBUILD_RESOLVED_SOURCE_VERSION --description "" --template-body file://templates/webops.yaml --capabilities CAPABILITY_NAMED_IAM
