@echo off
REM ====================================================================
REM  TESTE DE UM CONTRATO - Luz para Todos (UCs/ODIs via SQL-SSRS)
REM  COMO USAR: de dois cliques, digite o codigo do contrato e tecle Enter.
REM  Ex.: ECO 044/2026
REM  Baixa SO esse contrato (ignorando o estado anterior) e em seguida
REM  reconsolida a base inteira a partir de todos os brutos ja existentes.
REM  Serve para validar contrato novo recem-incluido no ucs_map.json.
REM  Na 1a vez, instala sozinho o 'uv' (pode demorar um pouco a mais).
REM  Nao edite este arquivo.
REM ====================================================================
title Teste de contrato - Luz para Todos
cd /d "%~dp0"

set "CONTRATO="
set /p CONTRATO=Codigo do contrato (ex.: ECO 044/2026):

REM Sem codigo nao ha o que testar - sair aqui evita baixar os 24 contratos sem querer,
REM porque o pipeline trata --contratos vazio como "todos".
if "%CONTRATO%"=="" (
  echo.
  echo  Nenhum contrato informado. Nada foi executado.
  echo.
  pause
  exit /b 1
)

echo.
echo Baixando %CONTRATO% e reconsolidando a base...
echo.

powershell -ExecutionPolicy Bypass -File "run_ucs_com_uv_install.ps1" --contratos "%CONTRATO%" --refresh
set CODIGO=%ERRORLEVEL%

echo.
echo ====================================================================
if "%CODIGO%"=="0" (
  echo  CONCLUIDO COM SUCESSO. Pode fechar esta janela.
  echo  Confira no log quantas linhas vieram de %CONTRATO%.
) else (
  echo  ATENCAO: ocorreu um erro ^(codigo %CODIGO%^).
  echo  Tire um print desta tela e traga a pasta output_ucs de volta.
)
echo ====================================================================
echo.
pause
