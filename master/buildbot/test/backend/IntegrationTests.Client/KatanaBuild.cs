using System;
using System.Collections.Generic;
using System.Text;

namespace Unity.Katana.IntegrationTests.Client
{
    public class KatanaBuild
    {
        public KatanaBuilder Builder {get; set;} = null;

        public int Build { get; set; } = -1;
        public string Revision { get; set; }
        public string Prioirty { get; set; } = "50";
        public string Slave  { get; set; } = null;
        public string Reason { get; set; } = "IntegrationTest";
        public bool Force { get; set; } = true;
        public bool Running { get; set; } = false;
        public bool Stopping { get; set; } = false;
        public bool Stopped { get; set; } = true;
        public bool Starting { get; set; } = false;

        public KatanaBuild(KatanaBuilder builder, int build, string revision, string priority)
        {
            Builder = builder;
            Build = build;
            Revision = revision;
            Prioirty = priority;
        }

        public KatanaBuild(KatanaBuilder builder, string revision, string priority)
        {
            Builder = builder; 
            Revision = revision;
            Prioirty = priority;
        }

        public KatanaBuild(KatanaBuilder builder, string revision)
        {
            Builder = builder;
            Revision = revision;
        }

        public KatanaBuild(string revision)
        {            
            Revision = revision;
        }
        

    }
}
