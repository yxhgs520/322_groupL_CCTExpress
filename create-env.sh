#!/bin/bash
# 创建.env文件的Shell脚本

if [ -f .env ]; then
    echo ".env文件已存在，跳过创建。"
else
    cat > .env << EOF
# Django Settings
SECRET_KEY=django-insecure-your-secret-key-here-change-in-production
DEBUG=True

# OpenRouteService API Configuration (可选)
OPENROUTESERVICE_API_KEY=your-api-key-here
EOF
    echo ".env文件已创建！"
    echo "请根据需要编辑.env文件中的配置。"
fi

