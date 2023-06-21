#!/bin/sh

cp ./local/dotenv ./.env.backup
sed -i '/YC_API_ACCESS_KEY=/c\YC_API_ACCESS_KEY=<your-value>' ./local/dotenv
sed -i '/YC_API_SECRET_KEY=/c\YC_API_SECRET_KEY=<your-value>' ./local/dotenv
