using System;
using System.Collections.Generic;
using System.Text;

namespace Unity.Katana.IntegrationTests.Framework
{
    public static class CustomAssertionExtensions
    {
        /// <summary>
        /// http://www.planetgeek.ch/2012/03/22/how-to-suppress-exceptions-with-fluent-assertions/
        /// Can return void too.
        /// </summary>
        public static AssertionResult IgnoreAnyExceptions<TException>(this Action action)
            where TException : Exception
        {
            try
            {
                action();
                return new AssertionResult();
            }
            catch (TException e)
            {
                return new AssertionResult(false, e.Message);
            }
        }

        public static void AddResult(this AssertionResult result, List<string> resultList)
        {
            if (!result.Pass)
                resultList.Add(result.Message);
        }
    }
}
