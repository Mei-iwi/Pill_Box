param(
    [string]$BrokerHost='localhost',
    [string[]]$DeviceIds=@('PB01')
)
$ErrorActionPreference='Stop'
if(-not $DeviceIds.Count -or (@($DeviceIds | Select-Object -Unique).Count -ne $DeviceIds.Count) -or ($DeviceIds -contains 'gateway')){throw 'Provide unique device IDs; gateway is reserved'}
foreach($id in $DeviceIds){if($id -notmatch '^[A-Za-z0-9_-]{1,32}$'){throw 'Invalid device ID'}}
if($BrokerHost -notmatch '^[A-Za-z0-9.-]+$'){throw 'Use a hostname or IPv4 address for BrokerHost'}
Get-Command openssl,docker -ErrorAction Stop | Out-Null
$opensslExecutable=(Get-Command openssl.exe -ErrorAction Stop).Source
docker info --format '{{.ServerVersion}}' | Out-Null
if($LASTEXITCODE-ne 0){throw 'Start Docker Desktop before preparing deployment'}
$runtimePath=Join-Path $PSScriptRoot 'runtime'
if(Test-Path -LiteralPath $runtimePath){throw 'runtime already exists. Preserve the current keys; use another checkout for a fresh deployment.'}
New-Item -ItemType Directory -Path (Join-Path $runtimePath 'certs') -Force | Out-Null
function Invoke-PillboxOpenSSL([string[]]$Arguments){& $opensslExecutable @Arguments;if($LASTEXITCODE-ne 0){throw 'OpenSSL failed'}}
function RandomSecret(){return ((& $opensslExecutable rand -hex 32).Trim())}
$certs=Join-Path $runtimePath 'certs'
Invoke-PillboxOpenSSL -Arguments @('req','-x509','-newkey','rsa:3072','-nodes','-sha256','-days','365','-subj','/CN=Pillbox Care Local CA','-keyout',(Join-Path $certs 'ca.key'),'-out',(Join-Path $certs 'ca.crt'))
Invoke-PillboxOpenSSL -Arguments @('req','-newkey','rsa:2048','-nodes','-sha256','-subj',('/CN='+$BrokerHost),'-keyout',(Join-Path $certs 'server.key'),'-out',(Join-Path $certs 'server.csr'))
$ipAddress=$null
$extraSan=if([System.Net.IPAddress]::TryParse($BrokerHost,[ref]$ipAddress)){'IP:'+$BrokerHost}else{'DNS:'+$BrokerHost}
@("subjectAltName=DNS:broker,DNS:localhost,DNS:host.wokwi.internal,IP:127.0.0.1,$extraSan",'extendedKeyUsage=serverAuth','keyUsage=digitalSignature,keyEncipherment') | Set-Content -LiteralPath (Join-Path $certs 'server.ext') -Encoding ascii
Invoke-PillboxOpenSSL -Arguments @('x509','-req','-in',(Join-Path $certs 'server.csr'),'-CA',(Join-Path $certs 'ca.crt'),'-CAkey',(Join-Path $certs 'ca.key'),'-CAcreateserial','-out',(Join-Path $certs 'server.crt'),'-days','365','-sha256','-extfile',(Join-Path $certs 'server.ext'))
$gatewaySecret=RandomSecret
$passwords=@("gateway:$gatewaySecret")
$acl=@('user gateway','topic read pillbox/+/event','topic read pillbox/+/status','topic read pillbox/+/heartbeat','topic read pillbox/+/environment','topic write pillbox/+/command','')
$ca=Get-Content -LiteralPath (Join-Path $certs 'ca.crt') -Raw
foreach($id in $DeviceIds){
    $password=RandomSecret
    $passwords+=($id+':'+$password)
    $acl+=@("user $id","topic read pillbox/$id/command","topic write pillbox/$id/event","topic write pillbox/$id/status","topic write pillbox/$id/heartbeat","topic write pillbox/$id/environment",'')
    $prefix=if($id-eq 'PB01'){''}else{$id+'_'}
    @"
#pragma once
#define PILLBOX_DEVICE_ID "$id"
#define PILLBOX_SCHEDULE_PREFIX "$prefix"
#define PILLBOX_WIFI_SSID "YOUR_WIFI"
#define PILLBOX_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define PILLBOX_MQTT_HOST "$BrokerHost"
#define PILLBOX_MQTT_PORT 8883
#define PILLBOX_MQTT_TLS 1
#define PILLBOX_MQTT_USER "$id"
#define PILLBOX_MQTT_PASSWORD "$password"
static const char PILLBOX_BROKER_CA[] = R"PEM($ca)PEM";
#define PILLBOX_MQTT_CA_CERT PILLBOX_BROKER_CA
"@ | Set-Content -LiteralPath (Join-Path $runtimePath ('device-'+$id+'.h')) -Encoding ascii
}
[System.IO.File]::WriteAllText((Join-Path $runtimePath 'passwords'),(($passwords -join "`n")+"`n"),[System.Text.Encoding]::ASCII)
[System.IO.File]::WriteAllText((Join-Path $runtimePath 'acl'),(($acl -join "`n")+"`n"),[System.Text.Encoding]::ASCII)
# Hash in place inside the official broker image; passwords never appear in command arguments.
docker run --rm --mount "type=bind,source=$runtimePath,target=/work" eclipse-mosquitto:2 mosquitto_passwd -U /work/passwords
if($LASTEXITCODE-ne 0){throw 'Password hashing failed; do not start deployment'}
@("MQTT_USER=gateway",("MQTT_PASSWORD="+$gatewaySecret)) | Set-Content -LiteralPath (Join-Path $runtimePath 'gateway.env') -Encoding ascii
$auth=@{}
$auth[(RandomSecret)]=@{actor_id='ADMIN01';role='admin';devices=@($DeviceIds)}
$auth[(RandomSecret)]=@{actor_id='NURSE01';role='nurse';devices=@($DeviceIds)}
$auth[(RandomSecret)]=@{actor_id='FAMILY01';role='family';devices=@($DeviceIds[0])}
$auth | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtimePath 'auth.local.json') -Encoding ascii
Write-Output 'Prepared private deployment. Keys and credentials are only in deploy/runtime (gitignored).'
Write-Output 'Next: docker compose -f deploy/compose.yaml config; docker compose -f deploy/compose.yaml up -d --build'
