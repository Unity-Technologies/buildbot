using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net;
using System.Threading;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Serilog;
using Serilog.Sinks.SystemConsole;
using Serilog.Sinks.File;

namespace Unity.Katana.IntegrationTests.Client
{
    public class KatanaClient
    {
        private static string settingfile = "katana.settings.json";

        private static readonly HttpClient client;
        private static HttpClientHandler handler;        

        public string url { get; set; }

        static KatanaClient()
        {
            handler = new HttpClientHandler();            
            client = new HttpClient(handler);
            JObject settings = JObject.Parse(File.ReadAllText(settingfile));
            var name = settings["LogFileFolder"].ToString() +
                       $"katanaclientlog-{DateTime.UtcNow.ToUniversalTime().ToString("HHmmss")}.log";
            Log.Logger = new LoggerConfiguration()
                .WriteTo.Console()                
                .WriteTo.RollingFile(name)                
                .CreateLogger();
        }

        public void SetBaseAddress(string url)
        {
            Log.Information($"set base address {url}");
            if(client.BaseAddress == null) {
                client.BaseAddress = new Uri(url);
            }
        }


        public async Task<HttpResponseMessage> SendPostRequest(string url, string content, string contentType)
        {            
            var httpcontent = new StringContent(content, Encoding.UTF8, contentType);
            Log.Information($"Send POST to {url} with content {httpcontent}");
            HttpResponseMessage response = await client.PostAsync(url, httpcontent);
            return response;
        }
        #region predefined queries
        public async Task<HttpResponseMessage> GetAllBuilders()
        {
            SetContentType(ContentType.Json);
            var url = @"/json/builders/";
            Log.Information($"Read from {client.BaseAddress+url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetABuilderInfo(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        /// <summary>
        /// 
        /// </summary>
        /// <param name="builder"></param>
        /// <returns>JArray</returns>
        public async Task<HttpResponseMessage> GetCachedBuildsOfABuilder(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        /// <summary>
        /// 
        /// </summary>
        /// <param name="builder"></param>
        /// <returns>JObject with KVP pair</returns>
        public async Task<HttpResponseMessage> GetAllBuildsOfABuilder(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds/_all";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        /// <summary>
        /// 
        /// </summary>
        /// <param name="builder"></param>
        /// <param name="num"> either positive, a build number, or negative,a past build.Using &lt4 will give the last 4  builds.</param>
        /// <returns></returns>
        public async Task<HttpResponseMessage> GetABuildOfABuilder(string builder, int num)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds/{num.ToString()}";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetLatestChangesOfABuilder(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds/-1/sourcestamp/changes";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        /// <summary>vb
        /// //Builds without properties or steps
        /// </summary>
        /// <param name="builder"></param>
        /// <returns></returns>
        public async Task<HttpResponseMessage> GetBasicInfosOfBuilds(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds?props=0&steps=0";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetLastXBuilds(string builder, int X)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds?" + RepeatQuery("select={0}", X);
            Log.Information($"Read from {client.BaseAddress + url}");            
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetChangesOfLastXBuilds(string builder, int X)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds?" + RepeatQuery("select={0}/source_stamp/changes", X);
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetSlavesOfBuilder(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/slaves?buildsteps=0&buildprops=0";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetStartSlavesOfBuilder(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/startslaves?buildsteps=0&buildprops=0";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetBuilderAndItsSlaveInfo(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}?select=&select=slaves";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetSlaveInfo(string slave)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/slaves/{slave}?buildsteps=0&buildprops=0";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetBuildsOnSlave(string slave)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/slaves/{slave}/builds";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetBuilderOnSlave(string slave)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/slaves/{slave}/builders";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetLastXBuildsOnSlave(string slave, int num)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/slaves/{slave}/builds/<{num.ToString()}?buildsteps=1&buildprops=1";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetAllProjects()
        {
            SetContentType(ContentType.Json);
            var url = $"/json/projects/";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetAProjects(string project)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/projects/{project}";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetBuilderofProject(string project, string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/projects/{project}/{builder}?buildsteps=0&buildprops=0";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetBuildQueue()
        {
            SetContentType(ContentType.Json);
            var url = @"/json/buildqueue/";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetPendingBuilds(string builder)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/pending/{builder}/";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        public async Task<HttpResponseMessage> GetGlobalStatus()
        {
            SetContentType(ContentType.Json);
            var url = @"/json/globalstatus/";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }

        /// <summary>
        /// Return json of a build - cached to help debugging
        /// </summary>
        /// <param name="builder"></param>
        /// <param name="buildNumber"></param>
        /// <returns></returns>
        public async Task<HttpResponseMessage> GetBuild(string builder, int buildNumber)
        {
            SetContentType(ContentType.Json);
            var url = $"/json/builders/{builder}/builds/{buildNumber.ToString()}";
            Log.Information($"Read from {client.BaseAddress + url}");
            HttpResponseMessage response = await client.GetAsync(url);
            return response;
        }


        /// <summary>
        /// Give a revision number, to find its build number on a builder.
        /// </summary>
        /// <param name="revision"></param>
        /// <param name="builder"></param>
        /// <param name="num">How many build on that build will be searched, default 3</param>
        /// <returns></returns>
        public int GetBuildNumberFromRevision(string revision, string builder, int num = 3)
        {
            int buildnr = -1;
            var resp = GetLastXBuilds(builder, num);
            if (resp.Result.StatusCode != HttpStatusCode.OK)
            {
                Log.Warning($"Return {resp.Result.StatusCode}, " +
                            $"content: {resp.Result.Content.ReadAsStringAsync().Result}, try once again");
                resp = GetLastXBuilds(builder, num);
            }
            string resp_string = resp.Result.Content.ReadAsStringAsync().Result;
            CheckResponseIsJson(resp_string);

            var content = JObject.Parse(resp_string);
            Log.Information($"Getting {num} builds with revision {revision}.");
            for (int i = 1; i <= num; i++)
            {
                string iStr = (i * -1).ToString();
                string rev = string.Empty;
                try
                {
                    rev = content[iStr]["sourceStamps"][0]["revision_short"].ToString();
                }
                catch (Exception e)
                {
                    Log.Error($"Revision nunmber {revision} is not found in {i} : content is {content[iStr]}");
                    Log.Error(e.Message);
                    throw;
                }

                if (rev == revision)
                {
                    buildnr = (int)content[iStr]["number"];
                    Log.Information($"Find build number {builder}");
                    break;
                }
            }
            return buildnr;
        }

        


        /// <summary>
        /// Find the build number from revision number and start and stop time
        /// Make sure only the recently start or stopped build are found
        /// </summary>
        /// <param name="revision"></param>
        /// <param name="builder"></param>
        /// <param name="typeoftime">0: build start time,  1: build finish time</param>
        /// <param name="interval">the offset of current time and selected timestamp</param>
        /// <param name="num">how many builds are searched</param>
        /// <returns></returns>
        public int GetBuildNumberFromRevisionAndTime(string revision,
                                                     string builder,
                                                     int typeoftime = 0,
                                                     int interval = 20, 
                                                     int num = 3)
        {
            int buildnr = -1;
            var resp = GetLastXBuilds(builder, num);
            if (resp.Result.StatusCode != HttpStatusCode.OK)
            {
                Log.Warning($"Return {resp.Result.StatusCode}, " +
                            $"content: {resp.Result.Content.ReadAsStringAsync().Result}, try once again");
                resp = GetLastXBuilds(builder, num);
            }
            CheckResponseIsJson(resp.Result.Content.ReadAsStringAsync().Result);
            JObject content = JObject.Parse(resp.Result.Content.ReadAsStringAsync().Result);
                        
            int time = 0;
            Log.Information($"Get {num} builds with revision {revision}.");
            for (int i = 1; i <= num; i++)
            {
                string iStr = (i * -1).ToString();
                string rev = string.Empty;
                try
                {
                    rev = content[iStr]["sourceStamps"][0]["revision_short"].ToString();
                }
                catch (Exception e)
                {
                    Log.Error($"Revision nunmber {revision} is not found in {i} : content is {content[iStr]}");
                    Log.Error(e.Message);
                    throw;
                }

                try
                {
                    double _time = 0;
                    if (typeoftime == 0)
                    {
                        if ((string)content[iStr]["times"][0] != null)
                        {
                            _time = (double)content[iStr]["times"][0];
                        }                        
                    }
                    else if (typeoftime == 1)
                    {
                        if ((string)content[iStr]["times"][1] != null)
                        {
                            _time = (double)content[iStr]["times"][1];
                        }                        
                    }                     
                    var _seconds = Math.Truncate(_time);
                    time = (int)_seconds;
                }
                catch (Exception e)
                {
                    Log.Error($"Finish time {time} is not found in {i} : content is {content[iStr]}");
                    Log.Error(e.Message);
                    throw;
                }

                var datanow = (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0)).TotalSeconds;
                var diff = datanow - time;
                Log.Debug($"Different is {diff}");

                if (rev == revision && diff <= interval)
                {
                    buildnr = (int)content[iStr]["number"];
                    Log.Information($"Found build number {buildnr}");
                    break;
                }
            }
            return buildnr;
        }

        /// <summary>
        /// Give a revision, retrun X number of 'build number' on that builder. 
        /// </summary>
        /// <param name="revision"></param>
        /// <param name="builder"></param>
        /// <param name="X">How many build numbers will be return.</param>
        /// <param name="num">How many builds will be searched on that builder, default is 3.</param>
        /// <returns></returns>
        /// <remarks>Possible in 'num' builds, there are less than X builds having the given revision number.</remarks>
        public List<int> GetXBuildNumberFromRevision(string revision, string builder, int X, int num = 3)
        {
            List<int> buildsnr = new List<int>();
            //List<int> buildsnr = Enumerable.Repeat(-1, X - 1).ToList();
            var resp = GetLastXBuilds(builder, num);
            if (resp.Result.StatusCode != HttpStatusCode.OK)
            {
                Log.Warning($"Return {resp.Result.StatusCode}, " +
                            $"content: {resp.Result.Content.ReadAsStringAsync().Result}, try once again");
                resp = GetLastXBuilds(builder, num);
            }
            CheckResponseIsJson(resp.Result.Content.ReadAsStringAsync().Result);
            JObject content = JObject.Parse(resp.Result.Content.ReadAsStringAsync().Result);
            Log.Information($"Get {num} build with revision {revision}.");
            //// Loop 'num' times, to find the build which has a match of revision number,  ////
            //// and add the build number into list ////
            for (int i = 1; i <= num; i++)
            {
                string iStr = (i * -1).ToString();
                string rev = string.Empty;
                try
                {
                    rev = content[iStr]["sourceStamps"][0]["revision_short"].ToString();
                }
                catch (Exception e)
                {                    
                    Log.Error($"Revision nunmber {revision} is not found in {i} : content is {content[iStr]}");
                    Log.Error(e.Message);
                    throw;
                }
                    

                if (rev == revision)
                {
                    buildsnr.Add((int)content[iStr]["number"]);
                    Log.Information($"Found and Added build number {(int)content[iStr]["number"]}");
                    if (buildsnr.Count >= X)
                    {
                        break;
                    }                                       
                }
            }

            //// If less than X match find, padding -1 in to the list ////
            if (buildsnr.Count < X )
            {
                for (int i = buildsnr.Count; i < X; i++)
                {
                    buildsnr[i] = -1;
                    Log.Warning("Not enough valid build numbers are found, add -1 into list");
                }
            }

            return buildsnr;
        }

        #endregion


        #region Predefine actions
        public async Task<HttpResponseMessage> LaunchBuild(string project,
                                                   string builder,
                                                   string branch,
                                                   string revision,
                                                   string priority,
                                                   string slave = null,
                                                   string reason = "IntegrationTest",
                                                   bool force = true)
        {
            string action = $"/projects/{project}/builders/{builder}/force?{project.ToLower()}_branch={branch}" +  $"&returnpage=pending_json";

            var slctslave = slave == null ? "default" : slave;
            List<string> payload = new List<string>();
            if (project == "Unity")
            {
                payload.Add($"forcescheduler={project.ToLower()}BuildersWithSmartSelect [force]");
            }
            else
            {
                payload.Add($"forcescheduler={project.ToLower()}+%5Bforce%5D");
            }            
            payload.Add($"selected_slave={slctslave}");
            payload.Add($"priority={priority}");
            payload.Add($"reason={reason}");
            payload.Add($"{project.ToLower()}_revision={revision}");
            if (force)
            {
                payload.Add("checkbox=force_rebuild");
            }
            
            string content = string.Join("&", payload);
            Log.Information($"Launch build on {client.BaseAddress + action}, with payload {content}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            return response;
        }

        public async Task<HttpResponseMessage> LaunchBuild(KatanaBuild katanabuild)
        {
            string project = katanabuild.Builder.Project;
            string builder = katanabuild.Builder.Builder;
            string branch = katanabuild.Builder.Branch;
            string slave = katanabuild.Slave;
            string priority = katanabuild.Prioirty;
            string reason = katanabuild.Reason;
            string revision = katanabuild.Revision;
            bool force = katanabuild.Force;

            string action = $"/projects/{project}/builders/{builder}/force?{project.ToLower()}_branch={branch}" + $"&returnpage=pending_json";

            var slctslave = slave == null ? "default" : slave;
            List<string> payload = new List<string>();
            if (project == "Unity")
            {
                payload.Add($"forcescheduler={project.ToLower()}BuildersWithSmartSelect [force]");
            }
            else
            {
                payload.Add($"forcescheduler={project.ToLower()}+%5Bforce%5D");
            }
            payload.Add($"selected_slave={slctslave}");
            payload.Add($"priority={priority}");
            payload.Add($"reason={reason}");
            payload.Add($"{project.ToLower()}_revision={revision}");
            if (force)
            {
                payload.Add("checkbox=force_rebuild");
            }

            string content = string.Join("&", payload);
            Log.Information($"Launch build on {client.BaseAddress + action}, with payload {content}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            katanabuild.Starting = true;
            katanabuild.Running = false;
            katanabuild.Stopped = false;
            katanabuild.Stopping = false;
            return response;
        }

        public async Task<HttpResponseMessage> Rebuild(string project, 
                                                       string builder, 
                                                       string branch, 
                                                       string build, 
                                                       string reason= "Backend Integration Test")
        {
            string action = $"/projects/{project}/builders/{builder}/builds/{build}/rebuild?" +
                $"{project.ToLower()}_branch={branch}&property1name=force_rebuild&property1value=True";
            string content = $"comments={reason}";
            Log.Information($"Rebuild on {client.BaseAddress + action}, with payload {content}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            return response;
        }

        public async Task<HttpResponseMessage> StopAllBuildOnBuilder(string project, string builder, string branch,
                                                                     bool isWaiting = true)
        {
            HttpResponseMessage response = await GetABuilderInfo(builder);
            if (response.StatusCode != HttpStatusCode.OK)
            {
                Log.Warning($"Return {response.StatusCode}, " +
                            $"content: {response.Content.ReadAsStringAsync().Result}, try once again");
                response = await GetABuilderInfo(builder);
            }
            HttpResponseMessage resp = null;
            CheckResponseIsJson(response.Content.ReadAsStringAsync().Result);
            var content = JObject.Parse(response.Content.ReadAsStringAsync().Result);
            Log.Information($"Read builder {builder} on {project}/{branch}");
            JArray currentBuilds = (JArray)content["currentBuilds"];            
            if (currentBuilds != null)
            {
                foreach (var currentBuild in currentBuilds)
                {
                    string build = currentBuild["number"].ToString();
                    Log.Information($"Stop build #{build} on {project}/{builder}/{branch}");
                    resp = await StopBuild(project, builder, build, branch, isWaiting);                    
                }                
            }
            return resp;
        }


        public async Task<HttpResponseMessage> StopBuild(string project, string builder, 
                                                         string build, string branch, bool  isWaiting = true)
        {
            string action = $"/projects/{project}/builders/{builder}/builds/{build}/stop?" +
                $"{project.ToLower()}_branch={branch}";
            string content = "comments=Backend Integration Test force to stop";
            Log.Information($"Stop build #{build} on {project}/{builder}/{branch}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            if (isWaiting)
            {
                await Task.Delay(1000);
            }            
            return response;
        }

        public async Task<HttpResponseMessage> StopBuild(KatanaBuild build, bool isWaiting = true)

        {
            string action = $"/projects/{build.Builder.Project}/builders/{build.Builder.Builder}" +
                $"/builds/{build.Build}/stop?{build.Builder.Project.ToLower()}_branch={build.Builder.Branch}";

            string content = "comments=Backend Integration Test force to stop";
            Log.Information($"Stop build #{build.Build} on {build.Builder.Project}/{build.Builder.Builder}" +
                $"/{build.Builder.Branch}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            if (isWaiting)
            {
                await Task.Delay(1000);
            }
            return response;
        }

        public async Task StopBuildAction(string project, string builder,
                                                         string build, string branch, bool isWaiting = true)
        {
            await StopBuild(project, builder, build, branch, isWaiting);
        }

        public async Task<HttpResponseMessage> StopBuild(string url, bool isWaiting = true)
        {            
            string content = "comments=Backend Integration Test force to stop";
            Log.Information($"Stop build at {url}");
            HttpResponseMessage response = await SendPostRequest(url, content, ContentType.wwwForm);
            if (true)
            {
                await Task.Delay(1000);
            }            
            return response;
        }

        public async Task<HttpResponseMessage> StopBuildChain(string project, string builder, 
                                                                string build, string branch, bool isWaiting = true)
        {
            string action = $"/projects/{project}/builders/{builder}/builds/{build}/stopchain?" +
                $"{project.ToLower()}_branch={branch}";
            string content = "comments=Backend Integration Test force to stop the build chain";
            Log.Information($"Stop build chain #{build} on {project}/{builder}/{branch}");
            HttpResponseMessage response = await SendPostRequest(action, content, ContentType.wwwForm);
            if (isWaiting)
            {
                await Task.Delay(1000);
            }            
            return response;
        }

        #endregion
        /// <summary>
        /// In order to implement the query which can retrieve information of last X times
        /// Generate the query by repeat the base 'query' by 'X' times,
        /// the parameter is increase from 1 to X or decrease from -1 to -X        
        /// </summary>
        /// <param name="query">the base query in string.Format() format</param>
        /// <param name="num">how many times to repeat</param>
        /// <param name="minus">Use positive or negitive number, default is true, means use negitive number</param>
        /// <returns>the query string</returns>
        /// <example> 
        /// RepeatQuery("select={0}", 3)  returns select = -1 & select = -2 & select = -3 
        /// RepeatQuery("select={0}", 3, false)  returns select = 1 & select = 2 & select = 3
        /// </example>
        private string RepeatQuery(string query, int num, bool minus = true)
        {
            var baseQuery = query;
            var mul = minus ? -1 : 1;
            for (int i = 1; i <= num; i++)
            {
                if (i == 1)
                {
                    query = string.Format(baseQuery + "&", (i * mul));
                }
                else if (i == num)
                {
                    query = query + string.Format(baseQuery, (i * mul));
                }
                else
                {
                    query = query + string.Format(baseQuery + "&", (i * mul));
                }
            }

            return query;            
        }

        private void SetContentType(string type)
        {
            var _mediatype = new MediaTypeWithQualityHeaderValue(type);
            if (!client.DefaultRequestHeaders.Accept.Contains(_mediatype))
            {
                client.DefaultRequestHeaders
                    .Accept
                    .Add(_mediatype);
                Log.Information($"Client does not have type {_mediatype.ToString()}, Add to header");
            }
            else
            {
                Log.Information($"Client has already had type {_mediatype.ToString()}.");
            }
        }

        private void CheckResponseIsJson(string resp)
        {
            try
            {
                Log.Information("Try to parse the string to JSON");
                JContainer.Parse(resp);
            }
            catch (Exception e)
            {
                Log.Error($"The return is not parseable, content is {resp}");
                Log.Error(e.Message);
                throw;
            }
        }

        public void Dispose()
        {
            client.Dispose();              
        }


    }
}
