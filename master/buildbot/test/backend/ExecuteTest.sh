cd IntegrationTests.Tests
dotnet xunit -notrait "Status=Unstable" -verbose -parallel none
cd -