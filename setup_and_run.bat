@echo off
chcp 65001 >nul
echo Iniciando EngineeringOS Core...

:: Executa diretamente o parser. 
:: Com a alteração no código acima, ele encontrará os imports.
python impl\src\eos_parser.py impl\seeds\matematica_base.eos

if %errorlevel% neq 0 (
    echo.
    echo Ocorreu um erro durante a execucao.
    echo Verifique se adicionou as linhas de sys.path no topo do eos_parser.py
) else (
    echo.
    echo Execucao finalizada com sucesso.
)
pause