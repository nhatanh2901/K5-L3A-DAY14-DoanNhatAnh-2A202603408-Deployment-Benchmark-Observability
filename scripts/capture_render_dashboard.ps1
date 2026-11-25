param([string]$OutputPath = '.lab-tools/render-dashboard-preview.png')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class LabRenderWindow {
    public delegate bool WindowCallback(IntPtr handle, IntPtr state);
    [DllImport("user32.dll")] public static extern bool EnumWindows(WindowCallback callback, IntPtr state);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr handle, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr handle, int command);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr handle, IntPtr after, int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll", EntryPoint="GetWindowLongW")] public static extern int GetWindowLong(IntPtr handle, int index);
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr handle, out Rect rect);
}
'@
Start-Process 'https://dashboard.render.com/web/srv-dc3b3vd9fdbs738cd310'
Start-Sleep -Seconds 7
$script:renderWindowHandle = [IntPtr]::Zero
$callback = [LabRenderWindow+WindowCallback]{
    param([IntPtr]$handle, [IntPtr]$state)
    $title = New-Object System.Text.StringBuilder 1024
    [void][LabRenderWindow]::GetWindowText($handle, $title, 1024)
    if ([LabRenderWindow]::IsWindowVisible($handle) -and $title.ToString() -match 'k5-day14-agent.*Render|Render.*k5-day14-agent') {
        $script:renderWindowHandle = $handle
        return $false
    }
    return $true
}
[void][LabRenderWindow]::EnumWindows($callback, [IntPtr]::Zero)
if ($script:renderWindowHandle -eq [IntPtr]::Zero) { throw 'Render service browser window not found; no screenshot taken.' }
[void][LabRenderWindow]::SetProcessDPIAware()
[void][LabRenderWindow]::SetThreadDpiAwarenessContext([IntPtr](-4))
[void][LabRenderWindow]::ShowWindow($script:renderWindowHandle, 3)
[void][LabRenderWindow]::SetForegroundWindow($script:renderWindowHandle)
$wasTopmost = ([LabRenderWindow]::GetWindowLong($script:renderWindowHandle, -20) -band 8) -ne 0
[void][LabRenderWindow]::SetWindowPos($script:renderWindowHandle, [IntPtr](-1), 0, 0, 0, 0, 0x43)
Start-Sleep -Seconds 2
$rect = New-Object LabRenderWindow+Rect
[void][LabRenderWindow]::GetWindowRect($script:renderWindowHandle, [ref]$rect)
$captureLeft = $rect.Left + 340
$captureTop = $rect.Top + 200
$bitmap = New-Object System.Drawing.Bitmap ($rect.Right - $captureLeft), ($rect.Bottom - $captureTop)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($captureLeft, $captureTop, 0, 0, $bitmap.Size)
    $bitmap.Save([System.IO.Path]::GetFullPath($OutputPath), [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
    if (-not $wasTopmost) {
        [void][LabRenderWindow]::SetWindowPos($script:renderWindowHandle, [IntPtr](-2), 0, 0, 0, 0, 0x43)
    }
}
Write-Output 'Captured the Render service browser window for review.'
