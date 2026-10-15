@echo off
REM ====================================================================
REM  Extracao UNICA 2023-2025 - Luz para Todos (UCs/ODIs via SQL-SSRS)
REM  COMO USAR: de dois cliques neste arquivo e aguarde terminar.
REM  Baixa os 24 contratos LPT operacionais em 2023-2025 e gera
REM  output\consolidado_ucs_2023-2025.csv.
REM  Se for interrompido, de dois cliques de novo: retoma do ponto onde parou.
REM  Na 1a vez, instala sozinho o 'uv' (pode demorar um pouco a mais).
REM  Nao edite este arquivo.
REM ====================================================================
title Extracao 2023-2025 - Luz para Todos
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -File "run_ucs_com_uv_install.ps1"
set CODIGO=%ERRORLEVEL%

echo.
echo ====================================================================
if "%CODIGO%"=="0" (
  echo  CONCLUIDO COM SUCESSO. Pode fechar esta janela.
) else (
  echo  ATENCAO: ocorreu um erro ^(codigo %CODIGO%^).
  echo  Tire um print desta tela e traga a pasta output de volta.
)
echo ====================================================================
echo.
pause
