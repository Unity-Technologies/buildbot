using System;

namespace Unity.Katana.IntegrationTests.Framework
{
    public class AssertionResult
    {
        public bool Pass { get; set; }
        public string Message { get; set; }

        public AssertionResult()
        {
            Pass = true;
            Message = string.Empty;
        }

        public AssertionResult(bool result, string msg)
        {
            Pass = result;
            Message = msg;
        }
    }
}
