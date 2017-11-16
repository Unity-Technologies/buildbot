using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Xunit;
using Xunit.Abstractions;
using Unity.Katana.IntegrationTests.Client;
using Unity.Katana.IntegrationTests.Framework;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using FluentAssertions;
using Xunit.Abstractions;
using Serilog;
using Serilog.Events;
using Serilog.Sinks.RollingFile;
using Serilog.Sinks.SystemConsole;
using Serilog.Sinks.XUnit;

namespace Unity.Katana.IntegrationTests.Tests
{
    public class ReliabilityTest : IntegrationTestsBase
    {
        private readonly ITestOutputHelper _output;
        public ReliabilityTest(ITestOutputHelper output)
        {
            this._output = output;
        }

        /// <summary>
        /// Start 5 builds and stop them. Repeat the test. 
        /// No builds should be stuck on slave
        /// </summary>
        /// <returns></returns>
        /// <remarks>There are async method not awaited, which is on purpose. Hope the behaviour can help 
        ///          trigger error </remarks>
        [Theory]
        [MemberData("Data_StopBuildWitRevisionReliabilityTest", MemberType = typeof(PropertyDataSource))]
        public async Task StopBuildWitRevisionReliabilityTest(KatanaBuilder katanabuilder, List<string> revision_list,
                                                              int round = 20)
        {
            #region arrange
            JObject settings = JObject.Parse(File.ReadAllText(settingfile));
            string logfilefolder = settings["LogFileFolder"].ToString();
            string testcasename = GetTestcaseName();
            string logfilename = SetupLogFileName(testcasename, logfilefolder);
            ILogger _logger = new LoggerConfiguration()
                            .WriteTo.Console()
                            .WriteTo.RollingFile(logfilename)
                            .WriteTo.TestOutput(_output, LogEventLevel.Verbose)
                            .CreateLogger();
            
            var client = new KatanaClient();

            string _baseAddress = settings["BaseAddress"].ToString();
            client.SetBaseAddress(_baseAddress);
            TestLog($"Set base address {_baseAddress}", _logger);
            var project = katanabuilder.Project;
            var builder = katanabuilder.Builder;
            var branch = katanabuilder.Branch;            
            Assert.True(revision_list.Count >= 5, "Test need at least 5 revision string");
            TestLog($"Read parameter project : {project}, builder: {builder}, branch: {branch}", _logger);
            bool isWaiting = false;
            await FreeAllSlavesOfABuilder(client, builder);
            #endregion

            #region action
            //// launch 5 setup builds to make the slave busy  ////
            for (int i = 0; i < round; i++)
            {
                await client.LaunchBuild(project, builder, branch, revision_list[0], "99");
                await client.LaunchBuild(project, builder, branch, revision_list[1], "99");
                await client.LaunchBuild(project, builder, branch, revision_list[2], "10");
                await client.LaunchBuild(project, builder, branch, revision_list[3], "90");
                await client.LaunchBuild(project, builder, branch, revision_list[4], "40");
                Thread.Sleep(10000);
                TestLog("5 builds are launched", _logger);

                bool isBuild1Stopped = false;
                bool isBuild2Stopped = false;
                bool isBuild3Stopped = false;
                bool isBuild4Stopped = false;
                bool isBuild5Stopped = false;

                int counter = 0;
                int build1 = -1;
                int build2 = -1;
                int build3 = -1;
                int build4 = -1;
                int build5 = -1;

                //// Wait until all the test build is running ////
                while (!isBuild1Stopped || !isBuild2Stopped || !isBuild3Stopped || !isBuild4Stopped || !isBuild5Stopped)
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");

                    //// Stop the setup builds if they are running ////
                    build1 = client.GetBuildNumberFromRevisionAndTime(revision_list[0], builder, 0, 40, 5);
                    build2 = client.GetBuildNumberFromRevisionAndTime(revision_list[1], builder, 0, 40, 5);
                    build3 = client.GetBuildNumberFromRevisionAndTime(revision_list[2], builder, 0, 40, 5);
                    build4 = client.GetBuildNumberFromRevisionAndTime(revision_list[3], builder, 0, 40, 5);
                    build5 = client.GetBuildNumberFromRevisionAndTime(revision_list[4], builder, 0, 40, 5);

                    if (build1 >= 0)
                    {
                        Func<Task> func =
                            async () => await client.StopBuild(project, builder, build1.ToString(), branch, isWaiting);

                        RunActionForXTimeAsync(func, 5);
                        TestLog($"Stopping build1 #{build1}", _logger);
                        //Thread.Sleep(1000);
                        isBuild1Stopped = true;
                    }
                    if (build2 >= 0)
                    {
                        Func<Task> func =
                            async () => await client.StopBuild(project, builder, build2.ToString(), branch, isWaiting);

                        RunActionForXTimeAsync(func, 5);
                        TestLog($"Stopping build2 #{build2}", _logger);
                        isBuild2Stopped = true;
                    }

                    if (build3 >= 0)
                    {
                        Func<Task> func =
                            async () => await client.StopBuild(project, builder, build3.ToString(), branch, isWaiting);

                        RunActionForXTimeAsync(func, 5);
                        TestLog($"Stopping build3 #{build3}", _logger);
                        isBuild3Stopped = true;

                    }
                    if (build4 >= 0)
                    {
                        Func<Task> func =
                            async () => await client.StopBuild(project, builder, build4.ToString(), branch, isWaiting);

                        RunActionForXTimeAsync(func, 5);
                        TestLog($"Stopping build4 #{build4}", _logger);
                        isBuild4Stopped = true;
                    }

                    if (build5 >= 0)
                    {
                        Func<Task> func =
                            async () => await client.StopBuild(project, builder, build5.ToString(), branch, isWaiting);

                        RunActionForXTimeAsync(func, 5);
                        TestLog($"Stopping build5 #{build5}", _logger);
                        isBuild5Stopped = true;
                    }
                    if (!isBuild1Stopped || !isBuild2Stopped ||
                        !isBuild3Stopped || !isBuild4Stopped || !isBuild5Stopped)
                        TestLog("not all the builds are stopped,   " +
                            $"build1: {isBuild1Stopped.ToString()}," +
                            $"build2: {isBuild2Stopped.ToString()}, " +
                            $"build3: {isBuild3Stopped.ToString()}, " +
                            $"build4: {isBuild4Stopped.ToString()}, " +
                            $"build5: {isBuild5Stopped.ToString()}" +
                            "refresh after 5 seconds", _logger);
                    Thread.Sleep(5000);
                }
                #endregion

                HttpResponseMessage resp = await client.GetCachedBuildsOfABuilder(builder);
                JArray builds = ParseJArrayResponse(resp);
                foreach (var build in builds)
                {
                    //"No builds has null result, meaning they are not running "
                    Assert.NotNull(build["results"]);
                }
                Thread.Sleep(5000);
            }
            #region clean up and assertion            
            
            #endregion
        }


        /// <summary>
        /// Launch 5 builds, and stop all the running builds, repeat 20 times
        /// </summary>
        /// <param name="katanabuilder"></param>
        /// <param name="revision_list"></param>
        /// <returns></returns>
        [Theory]
        [MemberData("Data_StopAllRunningBuildReliabilityTest", MemberType = typeof(PropertyDataSource))]
        public async Task StopAllRunningBuildReliabilityTest(KatanaBuilder katanabuilder, List<string> revision_list,
                                                             int round = 20)
        {
            #region arrange
            JObject settings = JObject.Parse(File.ReadAllText(settingfile));
            string logfilefolder = settings["LogFileFolder"].ToString();
            string testcasename = GetTestcaseName();
            string logfilename = SetupLogFileName(testcasename, logfilefolder);
            ILogger _logger = new LoggerConfiguration()
                            .WriteTo.Console()
                            .WriteTo.RollingFile(logfilename)
                            .WriteTo.TestOutput(_output, LogEventLevel.Verbose)
                            .CreateLogger();
            
            var client = new KatanaClient();

            
            string _baseAddress = settings["BaseAddress"].ToString();
            client.SetBaseAddress(_baseAddress);
            TestLog($"Set base address {_baseAddress}", _logger);
            var project = katanabuilder.Project;
            var builder = katanabuilder.Builder;
            var branch = katanabuilder.Branch;            
            Assert.True(revision_list.Count >= 5, "Test need at least 5 revision string");
            TestLog($"Read parameter project : {project}, builder: {builder}, branch: {branch}", _logger);
            bool isWaiting = false;            
            HttpResponseMessage resp = null;
            JObject builds = null;
            //await FreeAllSlavesOfABuilder(client, builder);
            #endregion

            #region action
            //// launch 5 setup builds to make the slave busy  ////
            for (int i = 0; i < round; i++)
            {
                await client.LaunchBuild(project, builder, branch, revision_list[0], "99");
                await client.LaunchBuild(project, builder, branch, revision_list[1], "99");
                await client.LaunchBuild(project, builder, branch, revision_list[2], "10");
                await client.LaunchBuild(project, builder, branch, revision_list[3], "90");
                await client.LaunchBuild(project, builder, branch, revision_list[4], "40");
                Thread.Sleep(10000);
                TestLog("5 builds are launched", _logger);

                bool isRunningOrPendingBuild = true;
                int counter = 0;
                //// Wait until all the test build is running ////
                while (isRunningOrPendingBuild)
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");
                    resp = await client.GetAllBuildsOfABuilder(builder);
                    builds = ParseJObjectResponse(resp);
                    bool _isRunningbuild = false;
                    foreach (var kvp in builds)
                    {
                        JObject build = (JObject)kvp.Value;
                        if (string.IsNullOrEmpty(build["results"].ToString()) || (int)build["results"] == 9)
                        {
                            _isRunningbuild = true;
                            if (build["number"] != null)
                            {
                                int buildnr = (int)build["number"];
                                Func<Task> func =
                                            async () =>
                                            await client.StopBuild(project, builder,
                                                                   buildnr.ToString(), branch, isWaiting);
                                TestLog($"Stop build#{buildnr}", _logger);

                                RunActionForXTimeAsync(func, 5);
                            }
                        }
                        else
                        {
                            TestLog($"Builds#{build["number"].ToString()} has result : {build["results"]}", _logger);
                        }
                    }

                    resp = await client.GetCachedBuildsOfABuilder(builder);
                    JArray buildsArray = ParseJArrayResponse(resp);
                    foreach (var build in buildsArray)
                    {
                        if (string.IsNullOrEmpty(build["results"].ToString()))
                        {
                            _isRunningbuild = true;
                            if (build["number"] != null)
                            {
                                int buildnr = (int)build["number"];
                                Func<Task> func =
                                            async () =>
                                            await client.StopBuild(project, builder,
                                                                   buildnr.ToString(), branch, isWaiting);
                                TestLog($"Stop build#{buildnr}", _logger);
                                RunActionForXTimeAsync(func, 5);
                            }
                        }
                        else
                        {
                            TestLog($"Builds#{build["number"].ToString()} has result : {build["results"]}", _logger);
                        }
                    }

                    bool _isPendingbuild = false;
                    resp = await client.GetPendingBuilds(builder);
                    JArray pendingBuilds = ParseJArrayResponse(resp);
                    if (pendingBuilds.Count > 0)
                    {
                        _isPendingbuild = true;
                        TestLog($"{pendingBuilds.Count} builds are pending.", _logger);
                    }

                    isRunningOrPendingBuild = _isRunningbuild || _isPendingbuild;
                    TestLog($"Running build: {_isRunningbuild.ToString()}, Pending build: {_isPendingbuild.ToString()}",
                            _logger);
                    Thread.Sleep(5000);
                }

            }
            #endregion
            #region clean up and assertion            
            resp = await client.GetAllBuildsOfABuilder(builder);
            builds = ParseJObjectResponse(resp);
            foreach (var kvp in builds)
            {
                //"No builds has null result, meaning they are not running "
                JObject build = (JObject)kvp.Value;
                TestLog($"Result is {build["results"]}", _logger);
                Assert.NotNull(build["results"]);
            }            
            
            //await client.StopAllBuildOnBuilder(project, builder, branch);            
            #endregion
        }


        /// <summary>
        /// Launch builds on muiltple builders, and stop them. repeat 20 times
        /// </summary>
        /// <returns></returns>
        [Theory]
        [MemberData("Data_StopBuildsOnMultipleBuilder", MemberType = typeof(PropertyDataSource))]        
        public async Task StopBuildsOnMultipleBuilder(List<KatanaBuild> katanabuilds, int round = 20)
        {
            #region arrange
            JObject settings = JObject.Parse(File.ReadAllText(settingfile));
            string logfilefolder = settings["LogFileFolder"].ToString();
            string testcasename = GetTestcaseName();
            string logfilename = SetupLogFileName(testcasename, logfilefolder);
            ILogger _logger = new LoggerConfiguration()
                            .WriteTo.Console()
                            .WriteTo.RollingFile(logfilename)
                            .WriteTo.TestOutput(_output, LogEventLevel.Verbose)
                            .CreateLogger();
            var client = new KatanaClient();
            
            string _baseAddress = settings["BaseAddress"].ToString();
            client.SetBaseAddress(_baseAddress);
            TestLog($"Set base address {_baseAddress}", _logger);            
            
            bool isWaiting = false;            
            #endregion

            for (int i = 0; i < round; i++)
            {
                TestLog($"Iteration # {i}", _logger);
                foreach (var katanabuild in katanabuilds)
                {
                    await FreeAllSlavesOfABuilder(client, katanabuild.Builder.Builder);
                    await client.LaunchBuild(katanabuild);
                    TestLog($"Read parameter project : {katanabuild.Builder.Project}, " +
                                                   $"builder: {katanabuild.Builder.Builder}, " +
                                                   $"branch: {katanabuild.Builder.Branch}" +
                                                   $"revision: {katanabuild.Revision}", 
                                                   _logger);

                    Thread.Sleep(1000);
                }

                int counter = 0;


                while (katanabuilds.Any(s => !s.Stopping))
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");

                    //// Stop the setup builds if they are running ////
                    foreach (var katanabuild in katanabuilds)
                    {
                        katanabuild.Build =
                            client.GetBuildNumberFromRevisionAndTime(katanabuild.Revision,
                                                                    katanabuild.Builder.Builder, 0, 50, 3);
                        TestLog($"{katanabuild.Builder.Builder} has start a build with number {katanabuild.Build}", 
                                _logger);
                        if (katanabuild.Build >= 0)
                        {
                            Func<Task> func = async () => await client.StopBuild(katanabuild, isWaiting);
                            await RunActionForXTimeAsync(func, 5);
                            TestLog($"Stopping build #{katanabuild.Build}", _logger);
                            katanabuild.Starting = false;
                            katanabuild.Running = false;
                            katanabuild.Stopped = false;
                            katanabuild.Stopping = true;
                        }
                    }

                    if (katanabuilds.Any(s => !s.Stopping))
                    {
                        TestLog("not all the builds are stopped, refresh after 5 seconds : ", _logger);
                        foreach (var katanabuild in katanabuilds)
                        {
                            TestLog($"Build#{katanabuild.Build} : {katanabuild.Stopping.ToString()}", _logger);
                        }
                    }                    
                }

                foreach (var katanabuild in katanabuilds)
                {
                    HttpResponseMessage resp = await client.GetCachedBuildsOfABuilder(katanabuild.Builder.Builder);
                    JArray builds_array = ParseJArrayResponse(resp);
                    foreach (var build in builds_array)
                    {
                        //"No builds has null result, meaning they are not running "
                        Assert.NotNull(build["results"]);
                    }
                }
                Thread.Sleep(5000);
            }
            
            #region clean up and assertion                        
            #endregion
        }

        [Fact]
        [Trait("Status", "Unstable")]
        public async Task ReprocudeRacingErrorTest()
        {
            for (int i = 0; i < 100; i++)
            {
                #region arrange
                string testcasename = GetTestcaseName();
                TextWriterTraceListener myTextListener = SetupTraceFile($"{testcasename}.log");
                var client = new KatanaClient();

                JObject settings = JObject.Parse(File.ReadAllText(settingfile));
                string _baseAddress = settings["BaseAddress"].ToString();
                client.SetBaseAddress(_baseAddress);
                Trace.WriteLine($"Set base address {_baseAddress}");
                //var setup = settings["TestSetup"].Where(x => (string)x["name"] == testcasename).ToArray().First();
                var project = "Unity";
                var builder = "proj0-Test DeploymentTests - Services - Tizen";
                var branch = "trunk";
                //JArray revisions = (JArray)setup["revisions"];
                List<string> revision_list = new List<string>()
            {
                "24c95392f5c2",
                "8d4e8eefeb52",
                "32e0dff84ceb",
                "9683b9f88e0e",
                "43294e7c9854"};


                Assert.True(revision_list.Count >= 5, "Test need at least 5 revision string");
                Trace.WriteLine($"Read parameter project : {project}, builder: {builder}, branch: {branch}");
                //await FreeAllSlavesOfABuilder(client, builder);
                #endregion

                #region action
                //// launch 2 setup builds to make the slave busy  ////
                await client.LaunchBuild(project, builder, branch, revision_list[0], "99");
                await client.LaunchBuild(project, builder, branch, revision_list[1], "99");
                Trace.WriteLine("Two setup builds are launched");
                Thread.Sleep(3000);
                //// launch 3 test builds. ////
                await client.LaunchBuild(project, builder, branch, revision_list[2], "10");
                await client.LaunchBuild(project, builder, branch, revision_list[3], "90");
                await client.LaunchBuild(project, builder, branch, revision_list[4], "40");
                Trace.WriteLine("Three setup builds are launched");

                bool isBuild1Stopped = false;
                bool isBuild2Stopped = false;
                int counter = 0;
                int build1 = -1;
                int build2 = -1;
                int build3 = -1;

                //// Wait until all the test build is running ////
                while (!isBuild1Stopped || !isBuild2Stopped)
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");

                    //// Stop the setup builds if they are running ////
                    build1 = client.GetBuildNumberFromRevision(revision_list[0], builder);
                    build2 = client.GetBuildNumberFromRevision(revision_list[1], builder);
                    if (build1 >= 0)
                    {
                        client.StopBuild(project, builder, build1.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build1}");
                        //Thread.Sleep(1000);
                        isBuild1Stopped = true;
                    }
                    if (build2 >= 0)
                    {
                        client.StopBuild(project, builder, build2.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build2}");
                        //Thread.Sleep(1000);
                        isBuild2Stopped = true;
                    }

                    Thread.Sleep(2000);
                }

                isBuild1Stopped = false;
                isBuild2Stopped = false;
                bool isBuild3Stopped = false;
                counter = 0;
                while (!isBuild1Stopped || !isBuild2Stopped || !isBuild3Stopped)
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");
                    //// Read the build number ////
                    int _build1 = client.GetBuildNumberFromRevision(revision_list[2], builder);
                    int _build2 = client.GetBuildNumberFromRevision(revision_list[3], builder);
                    int _build3 = client.GetBuildNumberFromRevision(revision_list[4], builder);

                    if (_build1 >= 0)
                    {
                        build1 = _build1;
                        client.StopBuild(project, builder, build1.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build1}");
                        //Thread.Sleep(1000);
                        isBuild1Stopped = true;

                    }
                    if (_build2 >= 0)
                    {
                        build2 = _build2;
                        client.StopBuild(project, builder, build2.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build2}");
                        //Thread.Sleep(1000);
                        isBuild2Stopped = true;
                    }

                    if (_build3 >= 0)
                    {
                        build3 = _build3;
                        client.StopBuild(project, builder, build3.ToString(), branch);
                        Console.WriteLine($"Stopping build {build3}");
                        //Thread.Sleep(1000);
                        isBuild3Stopped = true;
                    }

                    Trace.WriteLine($"builds number : {build1}, {build2}, {build3}");
                    if (!isBuild1Stopped || !isBuild2Stopped || !isBuild3Stopped)
                        Trace.WriteLine("not all the builds are running,  refresh after 5 seconds");
                    Thread.Sleep(2000);
                }
                #endregion

                #region clean up and assertion            
                WriteTraceToFile(myTextListener);
                //await client.StopAllBuildOnBuilder(project, builder, branch);            
                #endregion
            }

        }

        [Fact]
        [Trait("Status", "Unstable")]
        public async Task TriggerBuildToReproduceErrorTest()
        {
            for (int i = 0; i < 100; i++)
            {
                #region arrange
                TextWriterTraceListener myTextListener = SetupTraceFile("TriggerBuildTest.log");
                var client = new KatanaClient();

                JObject settings = JObject.Parse(File.ReadAllText(settingfile));
                string _baseAddress = settings["BaseAddress"].ToString();
                client.SetBaseAddress(_baseAddress);
                Trace.WriteLine($"Set base address {_baseAddress}");
                //var setup = settings["TestSetup"].Where(x => (string)x["name"] == "default").ToArray().First();
                var project = "Unity";
                var builder = "proj0-Test DeploymentTests - Services - Tizen";
                var branch = "trunk";
                Trace.WriteLine($"Read parameter project : {project}, builder: {builder}, branch: {branch}");

                #endregion

                #region action
                //// launch 2 setup builds to make the slave busy  ////
                await client.LaunchBuild(project, builder, branch, "24c95392f5c2", "99");
                await client.LaunchBuild(project, builder, branch, "8d4e8eefeb52", "99");
                Trace.WriteLine("Two setup builds are launched");
                Thread.Sleep(3000);
                //// launch 3 test builds. ////
                await client.LaunchBuild(project, builder, branch, "32e0dff84ceb", "10");
                await client.LaunchBuild(project, builder, branch, "9683b9f88e0e", "90");
                await client.LaunchBuild(project, builder, branch, "43294e7c9854", "40");
                Trace.WriteLine("Three setup builds are launched");

                bool isAllRunning = false;
                int counter = 0;
                int build1 = -1;
                int build2 = -1;
                int build3 = -1;

                //// Wait until all the test build is running ////
                while (!isAllRunning)
                {
                    counter++;
                    if (counter > 60)
                        Assert.True(false, "Testcase failed after running for 5 minutes");

                    //// Stop the setup builds if they are running ////
                    build1 = client.GetBuildNumberFromRevision("24c95392f5c2", builder);
                    build2 = client.GetBuildNumberFromRevision("8d4e8eefeb52", builder);
                    if (build1 >= 0)
                    {
                        await client.StopBuild(project, builder, build1.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build1}");
                    }
                    if (build2 >= 0)
                    {
                        await client.StopBuild(project, builder, build2.ToString(), branch);
                        Trace.WriteLine($"Stopping build {build2}");
                    }


                    //// Read the build number ////
                    build1 = client.GetBuildNumberFromRevision("32e0dff84ceb", builder);
                    build2 = client.GetBuildNumberFromRevision("9683b9f88e0e", builder);
                    build3 = client.GetBuildNumberFromRevision("43294e7c9854", builder);

                    isAllRunning = (build1 >= 0) && (build2 >= 0) && (build3 >= 0);
                    Trace.WriteLine($"builds number : {build1}, {build2}, {build3}");
                    if (!isAllRunning)
                        Trace.WriteLine($"not all the builds are running, {build1}, {build2} {build3}, " +
                            $"refresh after 5 seconds");
                    Thread.Sleep(5000);
                }
                #endregion

                #region clean up and assertion            
                WriteTraceToFile(myTextListener);
                await client.StopAllBuildOnBuilder(project, builder, branch);
                (build1 > build3 && build3 > build2).Should().BeTrue("The build number should be ordered " +
                    "accodring to their priority");
                #endregion
            }
            Thread.Sleep(5000);
        }
    }
}
