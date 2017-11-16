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
    public class TriggerBuildsTest : IntegrationTestsBase
    {                
        ITestOutputHelper _output;

        public TriggerBuildsTest(ITestOutputHelper output)
        {
            this._output = output;
        }

        /// <summary>
        /// Trigger three builds with different priority
        /// Verify that the execution order follows the priority
        /// </summary>        
        [Theory]
        [MemberData("Data_TriggerBuildTest", MemberType =typeof(PropertyDataSource))]
        public async Task TriggerBuildTest(KatanaBuilder katanabuilder, List<string> revision_list)
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
            TestLog($"Read parameter project : {project}, builder: {builder}, branch: {branch}", _logger, "Information");            
            await FreeAllSlavesOfABuilder(client, builder);
            #endregion

            #region action
            //// launch 2 setup builds to make the slave busy  ////
            await client.LaunchBuild(project, builder, branch, revision_list[0], "99");
            await client.LaunchBuild(project, builder, branch, revision_list[1], "99");
            TestLog("Two setup builds are launched", _logger, "Information");            
            Thread.Sleep(3000);
            //// launch 3 test builds. ////
            await client.LaunchBuild(project, builder, branch, revision_list[2], "10");
            await client.LaunchBuild(project, builder, branch, revision_list[3], "90");
            await client.LaunchBuild(project, builder, branch, revision_list[4], "40");
            TestLog("Three setup builds are launched", _logger);            

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
                build1 = client.GetBuildNumberFromRevisionAndTime(revision_list[0], builder, 0, 5);
                build2 = client.GetBuildNumberFromRevisionAndTime(revision_list[1], builder, 0, 30, 5);
                if (build1 >= 0)
                {
                    await client.StopBuild(project, builder, build1.ToString(), branch);
                    TestLog($"Stopping build {build1}", _logger);                    
                    Thread.Sleep(1000);
                    isBuild1Stopped = true;
                }
                if (build2 >= 0)
                {
                    await client.StopBuild(project, builder, build2.ToString(), branch);
                    TestLog($"Stopping build {build2}", _logger);                    
                    Thread.Sleep(1000);
                    isBuild2Stopped = true;
                }

                Thread.Sleep(5000);
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
                int _build1 = client.GetBuildNumberFromRevisionAndTime(revision_list[2], builder, 0, 40, 5);
                int _build2 = client.GetBuildNumberFromRevisionAndTime(revision_list[3], builder, 0, 20, 5);
                int _build3 = client.GetBuildNumberFromRevisionAndTime(revision_list[4], builder, 0, 30, 5);

                if (_build1 >= 0)
                {
                    build1 = _build1;
                    await client.StopBuild(project, builder, build1.ToString(), branch);
                    TestLog($"Stopping build {build1}", _logger);                    
                    Thread.Sleep(1000);
                    isBuild1Stopped = true;

                }
                if (_build2 >= 0)
                {
                    build2 = _build2;
                    await client.StopBuild(project, builder, build2.ToString(), branch);
                    TestLog($"Stopping build {build2}", _logger);                    
                    Thread.Sleep(1000);
                    isBuild2Stopped = true;
                }

                if (_build3 >= 0)
                {
                    build3 = _build3;
                    await client.StopBuild(project, builder, build3.ToString(), branch);
                    TestLog($"Stopping build {build3}", _logger);                    
                    Thread.Sleep(1000);
                    isBuild3Stopped = true;
                }

                TestLog($"builds number : {build1}, {build2}, {build3}", _logger);                

                if (!isBuild1Stopped || !isBuild2Stopped || !isBuild3Stopped)
                    TestLog("not all the builds are running,  refresh after 5 seconds", _logger);                    
                Thread.Sleep(5000);
            }
            #endregion

            #region clean up and assertion                        
            (build1 > build3 && build3 > build2).Should().BeTrue($"The build number {build2}, {build3}, {build1} should be in assending ordered " +
                "accodring to their priority");
            #endregion
        }

        

        /// <summary>
        /// Launch 3 build using same build, make sure the builds do not use other free slave
        /// Precondition: There are more than one slave free during test.
        /// </summary>
        /// <returns></returns>
        [Theory]
        [MemberData("Data_UseSpecifiedSlaveTest", MemberType = typeof(PropertyDataSource))]
        public async Task UseSpecifiedSlaveTest(KatanaBuilder katanabuilder,string revision_short)
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
            List<string> errmsgs = new List<string>();            
            var client = new KatanaClient();

            
            client.SetBaseAddress(settings["BaseAddress"].ToString());
            TestLog($"Logger: Set base address {settings["BaseAddress"].ToString()}", _logger);

            var project = katanabuilder.Project;
            var builder = katanabuilder.Builder;
            var branch = katanabuilder.Branch;                        
            await FreeAllSlavesOfABuilder(client, builder);
            #endregion
            #region action
            //// Step : Get the list of available 'build slaves' ////
            var resp = await client.GetSlavesOfBuilder(builder);            
            var content = JObject.Parse(resp.Content.ReadAsStringAsync().Result);
            List<string> freeSlaves = new List<string>();
            foreach (var slave in content)
            {
                JObject _slave = (JObject)slave.Value;
                if ((bool)_slave["connected"] )
                { 
                    if (_slave["runningBuilds"] == null || _slave["runningBuilds"].Count() == 0)
                    {
                        freeSlaves.Add(_slave["name"].ToString());
                        TestLog($"Build slave: {_slave["name"].ToString()} is free", _logger);                        
                    }
                    else
                    {
                        for (int i = 0; i < _slave["runningBuilds"].Count(); i++)
                        {
                            //// If there are not free slaves, Stop the builds on all the slaves ////
                            string url = _slave["runningBuilds"][i]["builder_url"].ToString();
                            url = url.Replace("?", "/stop?");
                            await client.StopBuild(url);
                            TestLog($"Try to stop the build on {_slave["name"].ToString()}", _logger);
                        }

                        Thread.Sleep(5000);

                        if (!(_slave["runningBuilds"] == null || _slave["runningBuilds"].Count() == 0))
                        {
                            freeSlaves.Add(_slave["name"].ToString());
                            TestLog($"No build on build slave: {_slave["name"].ToString()}, which is free now",_logger);
                        }
                        else
                        {
                            TestLog($"Build slave: {_slave["name"].ToString()} is not stoppable.", _logger, "Warning");
                        }
                    }
                }
                else
                {
                    TestLog($"Build slave: {_slave["name"].ToString()} is offline", _logger);
                }
            }

            //// Step: Get the list of 'processing slaves' ////
            resp = await client.GetStartSlavesOfBuilder(builder);
            content = JObject.Parse(resp.Content.ReadAsStringAsync().Result);
            List<string> processingSlaves = new List<string>();
            foreach (var slave in content)
            {
                JObject _slave = (JObject)slave.Value;
                if ((bool)_slave["connected"])
                {
                    processingSlaves.Add(_slave["name"].ToString());
                    TestLog($"Process Slave {_slave["name"].ToString()} is online", _logger);
                }
                else
                {
                    TestLog($"Process Slave {_slave["name"].ToString()} is offline", _logger);
                }
            }
                        
            //// Step : Launch 3 builds on the first build slave ////
            List<string> revisions = new List<string>() { revision_short };
            for (int i = 0; i < 3; i++)
            {
                await client.LaunchBuild(project, builder, branch, revisions[0], "90", freeSlaves.First());
                TestLog($"A build on builder {builder} of project {project} - branch {branch} is launched", _logger);
            }
            Thread.Sleep(3000);

            //// Stop: The builds take long time to build, stop them. ////
            bool isPengingBuild = true;
            while (isPengingBuild)
            {
                await StopCurrentBuildsIfPending(client, project, builder, branch, _logger);
                var response = client.GetPendingBuilds(builder);
                JArray contents = JArray.Parse(response.Result.Content.ReadAsStringAsync().Result);
                if (contents.Count < 1)
                {
                    isPengingBuild = false;
                }
            }

            var _build = client.GetBuildNumberFromRevision(revision_short, builder, 1);
            await client.StopBuild(project, builder, _build.ToString(), branch);


            //// Step : Wait all the builds are running ,and read their build number ////            
            List<int> builds = client.GetXBuildNumberFromRevision(revision_short, builder, 3);

            foreach (var item in builds)
            {
                TestLog($"A build is/was running with builder number {item}", _logger);
            }


            #endregion
            #region clean up and assertion

            //// Step: Check the builds is either running by select 'build slave'
            ////       or by a available 'processing slaves' in the list////
            //// Remark: If a correct revision is provide, the build slave is used, otherwise processing slave is used"
            foreach (var b in builds)
            {
                resp = await client.GetBuild(builder, b);
                content = JObject.Parse(resp.Content.ReadAsStringAsync().Result);
                var _slave = content["slave"].ToString();
                TestLog($"build number {b} used slave : {_slave} to build", _logger);
                bool _isContained = processingSlaves.Contains(_slave) || _slave == freeSlaves.First();
                _isContained. Invoking(t=>t.Should().
                     BeTrue("Builder should use a free slave either a build slave or a processing slaves"))
                    .IgnoreAnyExceptions<Xunit.Sdk.XunitException>()
                    .AddResult(errmsgs);
                                
            }
        
            await client.StopAllBuildOnBuilder(project, builder, branch);        
            AssertTestcase(errmsgs);
            #endregion
        }

        /// <summary>
        /// Rebuild a successful build.
        /// </summary>
        /// <param name="katanabuilder"></param>
        /// <param name="revision_short"></param>
        /// <returns></returns>

        [Theory]
        [MemberData("Data_RebuildTest", MemberType = typeof(PropertyDataSource))]
        public async Task RebuildTest(KatanaBuilder katanabuilder, string revision_short)
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
            
            List<string> errmsgs = new List<string>();
            //TextWriterTraceListener myTextListener = SetupTraceFile($"{testcasename}.log");
            var client = new KatanaClient();
            
            string _baseAddress = settings["BaseAddress"].ToString();
            client.SetBaseAddress(_baseAddress);
            TestLog($"Set base address {_baseAddress}", _logger);
            var project = katanabuilder.Project;
            var builder = katanabuilder.Builder;
            var branch = katanabuilder.Branch;
            TestLog($"Read parameter project : {project}, builder: {builder}, branch: {branch}", _logger);
            await FreeAllSlavesOfABuilder(client, builder);
            int cnt = 0;
            #endregion
            #region action

            //// Step : search a successful build, search cached builds first, if no successful build
            ////        then search all builds. If still no successful build, launch a new build            
            HttpResponseMessage resp = await client.GetCachedBuildsOfABuilder(builder);
            JArray buildsArray = ParseJArrayResponse(resp);
            int buildnr = -1;
            bool isSuccessBuildFound = false;
            foreach (var build in buildsArray)
            {                
                if ( (int)build["results"] == 0)
                {
                    buildnr = (int)build["number"];
                    isSuccessBuildFound = true;
                    TestLog($"build#{buildnr} was built succeessfully.", _logger);
                    break;
                }
            }

            if (!isSuccessBuildFound)
            {
                resp = await client.GetAllBuildsOfABuilder(builder);
                JObject buildsObject = ParseJObjectResponse(resp);
                foreach (var buildtoken in buildsObject)
                {
                    var build = buildtoken.Value;                    
                    if ((int)build["results"] == 0)
                    {
                        buildnr = (int)build["number"];
                        isSuccessBuildFound = true;
                        TestLog($"build#{buildnr} was built succeessfully.", _logger);
                        break;
                    }
                }
            }

            if (!isSuccessBuildFound)
            {
                await client.LaunchBuild(project, builder, branch, revision_short, "90", null, $"{testcasename}-1");
                TestLog($"A build on builder {builder} of project {project} - branch {branch} is launched", _logger);

                bool isBuildSuccess = false;
                cnt = 0;
                while (!isBuildSuccess && cnt < 120)
                {                    
                    
                    resp = await client.GetLastXBuilds(builder, 1);
                    JObject build= (JObject)ParseJObjectResponse(resp)["-1"];
                    if (build["results"] != null)
                    {
                        if ((int)build["results"] == 0 && (string)build["reason"] == $"{testcasename}-1")
                        {
                            buildnr = (int)build["number"];
                            isBuildSuccess = true;
                            TestLog($"New build#{buildnr} was built succeessfully.", _logger);
                            break;
                        }
                    }                    
                    
                    Thread.Sleep(5000);
                    cnt++;
                }
                Assert.True(isBuildSuccess, $"Couldn't make a build on builder {builder} in 10 minutes.");
            }

            resp = await client.Rebuild(project, builder, branch, buildnr.ToString(), $"{testcasename}-rebuild-1");
            resp = await client.Rebuild(project, builder, branch, buildnr.ToString(), $"{testcasename}-rebuild-2");
            resp = await client.Rebuild(project, builder, branch, buildnr.ToString(), $"{testcasename}-rebuild-3");
            TestLog($"Rebuild build#{buildnr}..", _logger);

            Thread.Sleep(10000);

            //// Step : Check the 2nd and 3rd are not found anywhare.  
            bool isDuplicatedRebuild = false;

            resp = await client.GetPendingBuilds(builder);
            JArray pendingBuilds = ParseJArrayResponse(resp);
            if (pendingBuilds.Count > 0)
            {
                foreach (var build in pendingBuilds)
                {
                    if ((string)build["reason"] == $"{testcasename}-rebuild-2" ||
                        (string)build["reason"] == $"{testcasename}-rebuild-3")
                    {
                        isDuplicatedRebuild = true;
                    }
                }
            }

            resp = await client.GetLastXBuilds(builder, 5);
            JObject lastFiveBuilds = ParseJObjectResponse(resp);
            foreach (var kvp in lastFiveBuilds)
            {
                var build = kvp.Value;
                if ((string)build["reason"] == $"{testcasename}-rebuild-2" ||
                    (string)build["reason"] == $"{testcasename}-rebuild-3")
                {
                    isDuplicatedRebuild = true;
                }
            }
        
            //// Step : Wait the rebuild finish.
            cnt = 0;
            bool isFirstBuildSuccess = false;                      
            while (cnt < 240)
            {                
                resp = await client.GetLastXBuilds(builder, 3);
                JObject builds = ParseJObjectResponse(resp);
                foreach (var kvp in builds)
                {
                    var build = kvp.Value;
                    if ((int)build["results"] == 0 && ((string)build["reason"]).Contains($"{testcasename}-rebuild-1"))
                    {
                        isFirstBuildSuccess = true;
                        TestLog($"New build#{buildnr} was rebuilt succeessfully.", _logger);
                    }
                    TestLog($"build has result {build["results"].ToString()}", _logger);
                }

                if (isFirstBuildSuccess)
                {
                    break;
                }

                Thread.Sleep(5000);
                cnt++;
            }

            isFirstBuildSuccess.Invoking(t => t.Should().BeTrue("Builds are not completed in 20 minutes"))
                                .IgnoreAnyExceptions<Xunit.Sdk.XunitException>()
                                .AddResult(errmsgs);

            isDuplicatedRebuild.Invoking(t => t.Should().BeFalse("No duplicated rebuild is launched"))
                                .IgnoreAnyExceptions<Xunit.Sdk.XunitException>()
                                .AddResult(errmsgs);

            #endregion

            #region cleanup and assertion
            await client.StopAllBuildOnBuilder(project, builder, branch);
            //WriteTraceToFile(myTextListener);
            AssertTestcase(errmsgs);
            #endregion

        }

        private void CreateBaseConfigFile(string config)
        {
            var assembly = GetType().GetTypeInfo().Assembly;
            string resourceKey = $"IntegrationTests.Tests.{config}";
            using (Stream resource = assembly.GetManifestResourceStream(resourceKey))
            {
                using (FileStream output = new FileStream(config, FileMode.Create))
                {
                    resource.CopyTo(output);
                }
            }
        }

    }
}
