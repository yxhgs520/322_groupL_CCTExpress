# 创建.env文件的PowerShell脚本

if (Test-Path .env) {
    Write-Host ".env文件已存在，跳过创建。" -ForegroundColor Yellow
} else {
    $envContent = @"
# Django Settings
SECRET_KEY=django-insecure-your-secret-key-here-change-in-production
DEBUG=True

# OpenRouteService API Configuration (可选)
OPENROUTESERVICE_API_KEY=your-api-key-here
"@
    $envContent | Out-File -FilePath .env -Encoding utf8
    Write-Host ".env文件已创建！" -ForegroundColor Green
    Write-Host "请根据需要编辑.env文件中的配置。" -ForegroundColor Cyan
}

