using System;
using System.Collections.Generic;

namespace Coffee.Reporting {
    public sealed class Dispatch {
        private readonly Action<string> send;
        private readonly List<string> delivered = new List<string>();

        public Dispatch(Action<string> send) {
            this.send = send;
        }

        public IReadOnlyList<string> Deliver(IEnumerable<string> receipts) {
            foreach (string receipt in receipts) {
                if (String.IsNullOrEmpty(receipt)) continue;
                send(receipt);
                delivered.Add(receipt);
            }
            return delivered.AsReadOnly();
        }
    }
}
