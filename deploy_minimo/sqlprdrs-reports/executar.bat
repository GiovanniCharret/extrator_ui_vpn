@echo off
REM ====================================================================
REM  RODADA DIARIA - Luz para Todos (UCs/ODIs via SQL-SSRS)
REM  COMO USAR: de dois cliques neste arquivo e aguarde terminar.
REM  Baixa TODOS os contratos vigentes do ucs_map.json e gera
REM  output_ucs\consolidado_ucs_modelo.csv.
REM  Sempre --refresh: dados frescos, o operador nao escolhe modo.
REM  Na 1a vez, instala sozinho o 'uv' (pode demorar um pouco a mais).
REM  Para validar UM contrato novo, use o testar_contrato.bat.
REM  Nao edite este arquivo.
REM ====================================================================
title Atualizacao das bases - Luz para Todos
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -File "run_ucs_com_uv_install.ps1" --refresh
set CODIGO=%ERRORLEVEL%

echo.
echo ====================================================================
if "%CODIGO%"=="0" (
  echo  CONCLUIDO COM SUCESSO. Pode fechar esta janela.
) else (
  echo  ATENCAO: ocorreu um erro ^(codigo %CODIGO%^).
  echo  Tire um print desta tela e traga a pasta output_ucs de volta.
)
echo ====================================================================
echo.
pause
