# SupportDesk AI Development PowerShell Script

param(
    [Parameter(Position=0)]
    [ValidateSet("format", "lint", "type", "test", "test-fast", "up", "down", "clean", "install", "migrate", "migrate-create", "health-check", "help")]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Name
)

function Show-Help {
    Write-Host "SupportDesk AI Development Commands" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage: .\scripts\dev.ps1 <command> [options]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available commands:" -ForegroundColor Cyan
    Write-Host "  format        - Format code with black and ruff"
    Write-Host "  lint          - Lint code with ruff"
    Write-Host "  type          - Type check with mypy"
    Write-Host "  test          - Run all tests"
    Write-Host "  test-fast     - Run fast tests only"
    Write-Host "  up            - Start services with docker-compose"
    Write-Host "  down          - Stop services"
    Write-Host "  clean         - Stop services and clean volumes"
    Write-Host "  install       - Install package in development mode"
    Write-Host "  migrate       - Run database migrations"
    Write-Host "  migrate-create - Create new migration (requires -Name parameter)"
    Write-Host "  health-check  - Test health endpoint"
    Write-Host "  help          - Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\scripts\dev.ps1 format"
    Write-Host "  .\scripts\dev.ps1 migrate-create -Name 'add_user_table'"
}

switch ($Command) {
    "format" { 
        Write-Host "Formatting code..." -ForegroundColor Green
        black src/ tests/
        ruff format src/ tests/
    }
    "lint" { 
        Write-Host "Linting code..." -ForegroundColor Green
        ruff check src/ tests/ 
    }
    "type" { 
        Write-Host "Type checking..." -ForegroundColor Green
        mypy src/ 
    }
    "test" { 
        Write-Host "Running all tests..." -ForegroundColor Green
        pytest -v 
    }
    "test-fast" { 
        Write-Host "Running fast tests..." -ForegroundColor Green
        pytest -m "not slow" -q 
    }
    "up" { 
        Write-Host "Starting services..." -ForegroundColor Green
        docker-compose up -d 
    }
    "down" { 
        Write-Host "Stopping services..." -ForegroundColor Green
        docker-compose down 
    }
    "clean" { 
        Write-Host "Cleaning up..." -ForegroundColor Green
        docker-compose down -v
        docker system prune -f
    }
    "install" { 
        Write-Host "Installing package..." -ForegroundColor Green
        pip install -e .[dev] 
    }
    "migrate" { 
        Write-Host "Running migrations..." -ForegroundColor Green
        alembic upgrade head 
    }
    "migrate-create" { 
        if (-not $Name) { 
            Write-Error "Migration name required: .\scripts\dev.ps1 migrate-create -Name 'migration_name'"
            exit 1
        }
        Write-Host "Creating migration: $Name" -ForegroundColor Green
        alembic revision --autogenerate -m $Name
    }
    "health-check" {
        Write-Host "Testing health endpoint..." -ForegroundColor Green
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -Method Get
            Write-Host "Health check successful:" -ForegroundColor Green
            $response | ConvertTo-Json -Depth 3
        } catch {
            Write-Host "Health check failed: $($_.Exception.Message)" -ForegroundColor Red
        }
        
        Write-Host "`nTesting root endpoint..." -ForegroundColor Green
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method Get
            Write-Host "Root endpoint successful:" -ForegroundColor Green
            $response | ConvertTo-Json -Depth 3
        } catch {
            Write-Host "Root endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    "help" { 
        Show-Help
    }
    default { 
        Write-Error "Unknown command: $Command"
        Show-Help
        exit 1
    }
}

if ($LASTEXITCODE -ne 0 -and $Command -ne "health-check") {
    Write-Error "Command failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
