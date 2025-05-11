# Prompt the user to specify the root directory
$rootDirectory = Read-Host "Please enter the root directory to search"

# Initialize an array to store the results
$nonPdfFiles = @()

# Recursively search for files that are not PDFs
Get-ChildItem -Path $rootDirectory -Recurse -File | ForEach-Object {
    if ($_.Extension -notin ".pdf", ".jpg", ".opf") {
        $nonPdfFiles += [PSCustomObject]@{
            Directory = $_.DirectoryName
            FileName  = $_.Name
            FileType  = $_.Extension
        }
    }
}

# Print the results in a formatted table
if ($nonPdfFiles.Count -gt 0) {
    $nonPdfFiles | Format-Table -AutoSize
} else {
    Write-Output "No non-PDF files found in the directory and its subdirectories."
}

Write-Output "Total number of non-PDF files found: $($nonPdfFiles.Count)"