cd IntegrationTests.Client
dotnet restore
dotnet build .
cd ../IntegrationTests.Framework
dotnet restore
dotnet build .
cd ../IntegrationTests.Tests
dotnet restore
dotnet build .