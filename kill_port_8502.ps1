# Script para liberar el puerto 8502 matando el proceso de Streamlit
$port = 8502
try {
    $processId = (Get-NetTCPConnection -LocalPort $port -ErrorAction Stop).OwningProcess
    if ($processId) {
        Write-Host "Matando proceso con PID $processId en el puerto $port..."
        Stop-Process -Id $processId -Force
        Write-Host "Proceso matado con éxito."
    }
} catch {
    Write-Host "No se encontró ningún proceso usando el puerto $port."
}
