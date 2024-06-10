#!/usr/bin/env bash

echo "Building for the PR branch"

aws cloudformation create-change-set \
  --stack-name Roles \
  --change-set-name $(echo $CODEBUILD_WEBHOOK_TRIGGER | tr '/' '-')-$CODEBUILD_RESOLVED_SOURCE_VERSION \
  --template-body file://output/stack-definitions/flooktech.yaml \
  --capabilities CAPABILITY_NAMED_IAM
