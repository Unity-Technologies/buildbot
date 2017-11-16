using System;
using System.Diagnostics;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Unity.Katana.IntegrationTests.Client;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Xunit;
using Xunit.Abstractions;
using Serilog;
using Serilog.Sinks.RollingFile;
using Serilog.Sinks.SystemConsole;
using Serilog.Sinks.XUnit;

[assembly: CollectionBehavior(DisableTestParallelization = true)]
namespace Unity.Katana.IntegrationTests.Tests
{
    public class IntegrationTestsBase
    {
        protected string settingfile = "test.json";

        protected void TestLog(string msg, ILogger logger, string level = "Information")
        {
            if (logger != null)
            {
                switch (level)
                {
                    case "Information":
                        logger.Information(msg);
                        break;
                    case "Warning":
                        logger.Warning(msg);
                        break;
                    case "Error":
                        logger.Error(msg);
                        break;
                    default:
                        logger.Information(msg);
                        break;
                }
                Trace.WriteLine(msg);
            }
            else
            {
                Trace.WriteLine("Logger is null, nothing logged");
            }
        }

        protected string SetupLogFileName(string testcasename, string folder = "")
        {
            string datetime = DateTime.UtcNow.ToUniversalTime().ToString("HHmmss");
            if (string.IsNullOrEmpty(folder))
            {
                return $"{testcasename}-{datetime}.log";
            }
            else
            {
                return $"{folder}{testcasename}-{datetime}.log";
            }
            
        }

        /// <summary>
        /// Setup the trace file for each testcase.
        /// </summary>
        /// <param name="filename"></param>
        /// <returns></returns>
        protected TextWriterTraceListener SetupTraceFile(string filename)
        {
            TextWriterTraceListener myTextListener = null;
            string datetime = DateTime.UtcNow.ToUniversalTime().ToString("ddMMyyyyHHmmss");            
            Stream myFileName = File.Create(filename.Replace(".log", $"{datetime}.log"));
            StreamWriter myOutputWriter = new StreamWriter(myFileName);
            myTextListener = new TextWriterTraceListener(myOutputWriter);
            Trace.Listeners.Add(myTextListener);
            return myTextListener;
        }

        /// <summary>
        /// Flush the trace to the file.
        /// </summary>
        /// <param name="myTextListener"></param>
        protected void WriteTraceToFile(TextWriterTraceListener myTextListener)
        {
            myTextListener.Flush();
            Trace.Listeners.Remove(myTextListener);
            myTextListener.Dispose();
        }

        /// <summary>
        /// After launch some builds, give a list of strings which are revisions of the builds. 
        /// Check if all the builds are up and running, and return the build number
        /// </summary>
        /// <param name="revision"></param>
        /// <param name="client"></param>
        /// <param name="builder"></param>
        /// <param name="method"></param>
        /// <param name="X"></param>
        /// <param name="num"></param>
        /// <returns>The build number</returns>
        /// <remarks> this method is not well tested.</remarks>
        protected List<int> WaitAllBuildsAreRunning(List<string> revision,
                                           KatanaClient client,
                                           string builder,
                                           Action method = null,
                                           int X = 3,
                                           int num = 10)
        {
            bool isAllRunning = false;
            int counter = 0;            
            List<int> builds = Enumerable.Repeat(-1, revision.Count).ToList();


            //// Wait until all the test build is running ////
            while (!isAllRunning)
            {
                counter++;
                if (method != null) {
                    method();
                }
                if (counter > 60)
                    new TimeoutException("Testcase failed after running for 5 minutes");


                WaitPendingBuildRequestListEmpty(client, builder, 5, revision);

                //// Read the build number ////                
                if (revision.Count > 1)
                {
                    for (int i = 0; i < builds.Count; i++)
                    {
                        builds[i] = client.GetBuildNumberFromRevision(revision[i], builder);
                    }
                }
                else
                {                    
                    builds = client.GetXBuildNumberFromRevision(revision[0], builder, X, num);
                }
                                
                if (!isAllRunning)
                {
                    Thread.Sleep(5000);
                }                
            }
            return builds;
        }


        /// <summary>
        /// Wait the pending build request list is empty, or there is not revision under test in the list.
        /// </summary>
        /// <param name="client"></param>
        /// <param name="builder"></param>
        /// <param name="t">timeout in minute</param>
        /// <param name="revisions"></param>
        public void WaitPendingBuildRequestListEmpty(KatanaClient client, 
                                                     string builder, 
                                                     int t = 5, 
                                                     List<string> revisions = null,
                                                     ILogger logger = null)
        {
            int cnt = 0;
            var response = client.GetPendingBuilds(builder);
            JArray contents = JArray.Parse(response.Result.Content.ReadAsStringAsync().Result);
            
            while (contents.Count > 0)
            {
                if (revisions.Count > 0)
                {
                    bool matchfound = false;
                    foreach (var content in contents)
                    {
                        var build_revision = content["source"]["revision_short"].ToString();
                        TestLog($"Found build revision {build_revision} on {builder}", logger);
                        if (revisions.Contains(build_revision))
                        {
                            matchfound = true;
                        }                        
                    }

                    if (!matchfound)
                    {
                        break;
                    }
                }

                cnt++;
                Thread.Sleep(5000);
                if (cnt > t * 12)
                {
                    break;
                }
                
            }
        }

        public async Task FreeAllSlavesOfABuilder(KatanaClient client,  string builder)
        {
            // Get the slaves of a builder
            // check the state of each slave
            // if the slave is not free, stop the build on it
            Task<HttpResponseMessage> resp = client.GetSlavesOfBuilder(builder);
            var slavearray = ParseJObjectResponse(resp.Result);
            await StopRunningBuildsOnAllSlave(client, slavearray);
            resp = client.GetStartSlavesOfBuilder(builder);
            slavearray = ParseJObjectResponse(resp.Result);
            await StopRunningBuildsOnAllSlave(client, slavearray);
            // risk: maybe there are multiple build on a slave, need check how to do that.
        }

        protected async Task StopRunningBuildsOnAllSlave(KatanaClient client, JObject slavearray, ILogger logger = null)
        {
            foreach (var kvp in slavearray)
            {
                string slavename = kvp.Key;
                JObject slave = (JObject)kvp.Value;
                JArray runningBuilds = (JArray)slave["runningBuilds"];
                if (runningBuilds != null)
                {
                    if (runningBuilds.Count() > 0)
                    {
                        TestLog($"Found {runningBuilds.Count()} builds are running on {slavename}.", logger);
                        foreach (var build in runningBuilds)
                        {
                            string buildurl = build["builder_url"].ToString();
                            string buildnr = build["number"].ToString();
                            TestLog($"Stop build number {buildnr} on {slavename}", logger);
                            buildurl.Replace("?", $"/builds/{buildnr}/stop?");
                            await client.StopBuild(buildurl);
                        }
                    }
                }
            }
        }


        /// <summary>
        /// Check the pending build request list, If there is a pending builds, stop the running build on the builder.
        /// </summary>
        /// <param name="client"></param>
        /// <param name="project"></param>
        /// <param name="builder"></param>
        /// <param name="branch"></param>
        public async Task StopCurrentBuildsIfPending(KatanaClient client,
                                                     string project, string builder, string branch,
                                                     ILogger logger = null)
        {
            var response = client.GetPendingBuilds(builder);
            string response_string = response.Result.Content.ReadAsStringAsync().Result;
            JArray contents = JArray.Parse(response_string);
            if (contents.Count > 0) {
                response = client.GetABuilderInfo(builder);
                var resp = JObject.Parse(response.Result.Content.ReadAsStringAsync().Result);
                foreach (var build in resp["currentBuilds"])
                {
                    string _nr = build["number"].ToString();
                    TestLog($"Stop builder number {_nr} on builder {builder}", logger);
                    await client.StopBuild(project, builder, _nr, branch);
                }                
            }
        }

        /// <summary>
        /// Get the current testcase name. 
        /// </summary>
        /// <param name="memberName"></param>
        /// <returns></returns>
        /// <see cref="https://stackoverflow.com/questions/41112381/get-the-name-of-the-currently-executing-method-in-dotnet-core"/>
        public string GetTestcaseName([System.Runtime.CompilerServices.CallerMemberName] string memberName = "")
        {            
            return memberName;
        }

        /// <summary>
        /// The next three methods are parse the response data to the corresponding JSON format. 
        /// </summary>
        /// <param name="resp"></param>
        /// <returns></returns>
        public JArray ParseJArrayResponse(HttpResponseMessage resp)
        {
            JArray result = null;
            var content = resp.Content.ReadAsStringAsync().Result;
            try
            {
               result = JArray.Parse(content);
            }
            catch (Exception e)
            {

                Debug.WriteLine($"{e.Message}: content is {content}");
                throw;
            }
            
            return result;
        }

        public JObject ParseJObjectResponse(HttpResponseMessage resp)
        {
            var content = resp.Content.ReadAsStringAsync().Result;
            JObject result = null;
            try
            {
                result = JObject.Parse(content);
            }
            catch (Exception e)
            {
                Debug.WriteLine($"{e.Message}: content is {content}");
                throw;
            }            
            return result;
        }

        public JToken ParseJContainerResponse(HttpResponseMessage resp)
        {
            var content = resp.Content.ReadAsStringAsync().Result;
            JToken result = JContainer.Parse(content);
            return result;
        }

        public void RunActionForXTimes(Action action, int x)
        {
            if (x <= 2)
            {
                x = 5;
            }
            else
            {
                for (int i = 0; i < x; i++)
                {
                    action();
                }
            }
        }

        public async Task RunActionForXTimeAsync(Func<Task> func, int x)
        {
            if (x <= 2)
            {
                x = 5;
            }
            else
            {
                for (int i = 0; i < x; i++)
                {
                    await func();
                }
            }
        }

        /// <summary>
        /// Assert the testcase by check the the number of element in errmsgs list 
        /// </summary>
        /// <param name="errmsgs"></param>
        public void AssertTestcase(List<string> errmsgs)
        {
            Assert.True(errmsgs.Count == 0,
                        string.Format("message: {0}", string.Join("; \r\n", errmsgs.Select(x => x).ToArray())));
        }
    }
}
