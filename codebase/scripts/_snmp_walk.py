import asyncio
from pysnmp.hlapi.asyncio import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, bulk_walk_cmd

async def walk(ip, community, oid):
    engine = SnmpEngine()
    target = await UdpTransportTarget.create((ip, 161))
    try:
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            engine,
            CommunityData(community, mpModel=1),
            target,
            ContextData(),
            0,
            25,
            ObjectType(ObjectIdentity(oid))
        ):
            if errorIndication:
                print('ERROR:', errorIndication)
                break
            elif errorStatus:
                print('ERROR:', errorStatus.prettyPrint())
                break
            else:
                for oid, value in varBinds:
                    print(f"{oid.prettyPrint()} = {value.prettyPrint()}")
    finally:
        engine.transportDispatcher.closeDispatcher()

asyncio.run(walk('10.40.123.246', 'public', '1.3.6.1.2.1.43.18.1.1'))
