local p = getAddress('"granblue_fantasy_relink.exe"+05E48188')

p = readPointer(p)
if p == nil or p == 0 then
  print("Failed at base pointer")
  return
end

p = readPointer(p + 0x2E8)
if p == nil or p == 0 then
  print("Failed at +0x2E8")
  return
end

p = readPointer(p + 0x78)
if p == nil or p == 0 then
  print("Failed at +0x78")
  return
end

local knownSlot = p + 0x504

local startAddr = knownSlot - 0x9000
local endAddr   = knownSlot + 0xA000

local minItemId = 1000
local maxItemId = 100000

local found = 0
local changed = 0

print(string.format("Known item address: %X", knownSlot))
print(string.format("Known item qty: %d", readInteger(knownSlot) or -1))
print(string.format("Scanning range: %X - %X", startAddr, endAddr))

for addr = startAddr, endAddr, 4 do
  local qty = readInteger(addr)
  local typ = readInteger(addr + 0x04)
  local itemId = readInteger(addr + 0x08)

  if qty and typ and itemId then
    if qty >= 1 and qty <= 999
       and typ == 12
       and itemId >= minItemId and itemId <= maxItemId then

      found = found + 1

      print(string.format(
        "Found #%03d addr=%X qty=%d type=%d itemId=%d",
        found,
        addr,
        qty,
        typ,
        itemId
      ))

      if qty < 999 then
        writeInteger(addr, 999)
        changed = changed + 1
        print(string.format("  -> Changed qty=%d -> 999", qty))
      else
        print("  -> Already 999, skipped")
      end
    end
  end
end

print(string.format("Total found items: %d", found))
print(string.format("Total changed items: %d", changed))
