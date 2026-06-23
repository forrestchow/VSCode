@echo off
chcp 65001 >nul
echo ========================================
echo  暗黑破坏神 自动按键 - 编译脚本
echo ========================================
echo.

set CSC="C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
set REFS=/reference:System.Windows.Forms.dll /reference:System.Drawing.dll

echo 编译中...
%CSC% /nologo /target:winexe %REFS% /out:diablo_auto_key.exe diablo_auto_key.cs

if %ERRORLEVEL% equ 0 (
    echo.
    echo ✅ 编译成功！生成: diablo_auto_key.exe
    echo.
    echo 双击 diablo_auto_key.exe 即可运行
) else (
    echo.
    echo ❌ 编译失败，错误码: %ERRORLEVEL%
)

pause
