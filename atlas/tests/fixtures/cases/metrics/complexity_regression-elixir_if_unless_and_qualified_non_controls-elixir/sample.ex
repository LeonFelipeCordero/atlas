def choose(x) do
 if x && ready do
 unless stopped || paused, do: accept(), else: reject()
 else
 fallback()
 end
 Client.if(x)
 Client.case(x)
end