using System;
using System.Collections.Generic;
using System.Text;

namespace Unity.Katana.IntegrationTests.Client
{
    public class KatanaBuilder
    {
        public string Project { get; set; }
        public string Branch { get; set; }
        public string Builder { get; set; }        

        public KatanaBuilder(string project, string builder, string branch)
        {
            Project = project;
            Branch = branch;
            Builder = builder;
        }
    }
}
