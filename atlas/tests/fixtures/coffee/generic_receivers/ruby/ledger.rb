class Ledger
  def record; end
end
class OtherLedger
  def record; end
end

def inferred
  ledger = Ledger.new
  ledger.record
end

def direct
  Ledger.new.record
end

def unknown(ledger)
  ledger.record
end

def factory
  ledger = make_ledger
  ledger.record
end

def reassigned
  ledger = Ledger.new
  ledger = make_ledger
  ledger.record
end

def other
  ledger = OtherLedger.new
  ledger.record
end

def block_defaults
  ledger = Ledger.new
  each do |ledger = nil|
    ledger.record
  end
end

def block_keywords
  ledger = Ledger.new
  each do |ledger: nil|
    ledger.record
  end
end

def block_destructured
  ledger = Ledger.new
  each do |(ledger, other)|
    ledger.record
  end
end

def brace_defaults
  ledger = Ledger.new
  each { |ledger = nil| ledger.record }
end

ledger = Ledger.new
def method_default(ledger = nil)
  ledger.record
end
def method_keyword(ledger: nil)
  ledger.record
end
def method_destructured((ledger, other))
  ledger.record
end

def conditional(flag)
  if flag
    ledger = Ledger.new
  end
  ledger.record
end
