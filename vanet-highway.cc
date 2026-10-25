/*
 * VANET highway scenario for "Performance Evaluation of VANETs for Traffic
 * Efficiency and Road Traffic Safety Using NS-3".
 *
 * Vehicles drive in both directions on a straight multi-lane highway, route
 * with AODV over an 802.11p-style radio, and exchange UDP traffic between
 * fixed vehicle pairs. One run measures packet delivery ratio (PDR), average
 * end-to-end delay, throughput and packet loss rate for the data flows and
 * appends them as one row to a CSV file.
 *
 * Example:
 *   ./ns3 run "vanet-highway --nVehicles=60 --speed=20 --dataRateKbps=100 --range=150 --RngRun=1"
 */

#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <cmath>
#include <fstream>
#include <map>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("VanetHighway");

// Vehicles that drive off one end of the highway re-enter at the other end,
// so the number of vehicles on the road (the density) stays constant.
static void
WrapPositions(NodeContainer vehicles, double length, Time interval)
{
    for (auto it = vehicles.Begin(); it != vehicles.End(); ++it)
    {
        Ptr<MobilityModel> mob = (*it)->GetObject<MobilityModel>();
        Vector pos = mob->GetPosition();
        if (pos.x > length)
        {
            pos.x -= length;
            mob->SetPosition(pos);
        }
        else if (pos.x < 0)
        {
            pos.x += length;
            mob->SetPosition(pos);
        }
    }
    Simulator::Schedule(interval, &WrapPositions, vehicles, length, interval);
}

int
main(int argc, char* argv[])
{
    uint32_t nVehicles = 60;
    double speed = 20.0;           // mean speed, m/s
    double speedSpread = 0.2;      // each vehicle drives at speed * U(1 - spread, 1 + spread)
    double dataRateKbps = 100.0;   // sending rate per flow
    double range = 150.0;          // communication range, m
    uint32_t nFlows = 10;
    uint32_t packetSize = 512;     // UDP payload, bytes
    double highwayLength = 2000.0; // m
    uint32_t lanesPerDirection = 2;
    double laneWidth = 5.0;  // m
    double txPowerDbm = 20.0;
    double simTime = 100.0;  // s
    double appStart = 10.0;  // s, flows start at a random time in [appStart, appStart + 1)
    double appStop = 95.0;   // s, leaves time for in-flight packets to arrive
    std::string experiment = "single";
    std::string csvFile = "vanet-results.csv";

    CommandLine cmd(__FILE__);
    cmd.AddValue("nVehicles", "Number of vehicles", nVehicles);
    cmd.AddValue("speed", "Mean vehicle speed (m/s)", speed);
    cmd.AddValue("speedSpread", "Relative speed spread around the mean (0.2 = +/-20%)", speedSpread);
    cmd.AddValue("dataRateKbps", "Sending rate per flow (kbit/s)", dataRateKbps);
    cmd.AddValue("range", "Communication range (m), hard cutoff", range);
    cmd.AddValue("nFlows", "Number of UDP flows", nFlows);
    cmd.AddValue("packetSize", "UDP payload size (bytes)", packetSize);
    cmd.AddValue("highwayLength", "Highway length (m)", highwayLength);
    cmd.AddValue("lanesPerDirection", "Lanes in each direction", lanesPerDirection);
    cmd.AddValue("txPower", "Transmit power (dBm)", txPowerDbm);
    cmd.AddValue("simTime", "Simulation time (s)", simTime);
    cmd.AddValue("appStart", "Time the flows start (s)", appStart);
    cmd.AddValue("appStop", "Time the flows stop (s)", appStop);
    cmd.AddValue("experiment", "Label written to the CSV (density, speed, load, range)", experiment);
    cmd.AddValue("csv", "CSV file the results row is appended to", csvFile);
    cmd.Parse(argc, argv);

    NS_ABORT_MSG_IF(nVehicles < 2, "need at least 2 vehicles");
    NS_ABORT_MSG_IF(nFlows > nVehicles, "nFlows must not exceed nVehicles");
    NS_ABORT_MSG_IF(appStart + 1 >= appStop || appStop >= simTime,
                    "need appStart + 1 < appStop < simTime");

    NodeContainer vehicles;
    vehicles.Create(nVehicles);

    // Mobility: random positions along the highway, half the lanes eastbound
    // and half westbound, each vehicle with a slightly different speed so
    // vehicles overtake each other.
    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    mobility.Install(vehicles);

    Ptr<UniformRandomVariable> xPos = CreateObject<UniformRandomVariable>();
    xPos->SetAttribute("Min", DoubleValue(0.0));
    xPos->SetAttribute("Max", DoubleValue(highwayLength));
    Ptr<UniformRandomVariable> vehicleSpeed = CreateObject<UniformRandomVariable>();
    vehicleSpeed->SetAttribute("Min", DoubleValue(speed * (1 - speedSpread)));
    vehicleSpeed->SetAttribute("Max", DoubleValue(speed * (1 + speedSpread)));

    uint32_t nLanes = 2 * lanesPerDirection;
    for (uint32_t i = 0; i < nVehicles; ++i)
    {
        uint32_t lane = i % nLanes;
        double direction = (lane < lanesPerDirection) ? 1.0 : -1.0;
        Ptr<ConstantVelocityMobilityModel> mob =
            vehicles.Get(i)->GetObject<ConstantVelocityMobilityModel>();
        mob->SetPosition(Vector(xPos->GetValue(), lane * laneWidth, 0.0));
        mob->SetVelocity(Vector(direction * vehicleSpeed->GetValue(), 0.0, 0.0));
    }
    Simulator::Schedule(Seconds(0.1), &WrapPositions, vehicles, highwayLength, Seconds(0.1));

    // Radio: the range is set with a hard-cutoff propagation model. Receivers
    // within `range` metres hear a frame, receivers further away hear nothing.
    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::RangePropagationLossModel", "MaxRange", DoubleValue(range));

    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    phy.Set("TxPowerStart", DoubleValue(txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(txPowerDbm));

    // 802.11p PHY (5.9 GHz band, 10 MHz channel, 6 Mbit/s) with an ad hoc MAC.
    // The wave module, which provided the 802.11p OCB MAC, is no longer in ns-3.
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211p);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue("OfdmRate6MbpsBW10MHz"),
                                 "ControlMode",
                                 StringValue("OfdmRate6MbpsBW10MHz"));
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer devices = wifi.Install(phy, mac, vehicles);

    // Routing: AODV.
    AodvHelper aodv;
    InternetStackHelper internet;
    internet.SetRoutingHelper(aodv);
    internet.Install(vehicles);

    Ipv4AddressHelper address;
    address.SetBase("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);

    // Traffic: nFlows distinct senders, each sending constant-rate UDP to a
    // different random vehicle.
    Ptr<UniformRandomVariable> pick = CreateObject<UniformRandomVariable>();
    std::vector<uint32_t> order(nVehicles);
    for (uint32_t i = 0; i < nVehicles; ++i)
    {
        order[i] = i;
    }
    for (uint32_t i = nVehicles - 1; i > 0; --i)
    {
        std::swap(order[i], order[pick->GetInteger(0, i)]);
    }

    Ptr<UniformRandomVariable> startJitter = CreateObject<UniformRandomVariable>();
    std::map<uint16_t, double> activeTime; // data port -> seconds the flow was sending
    for (uint32_t f = 0; f < nFlows; ++f)
    {
        uint32_t src = order[f];
        uint32_t dst = pick->GetInteger(0, nVehicles - 2);
        if (dst >= src)
        {
            dst++;
        }
        uint16_t port = 9000 + f;

        PacketSinkHelper sink("ns3::UdpSocketFactory",
                              InetSocketAddress(Ipv4Address::GetAny(), port));
        ApplicationContainer sinkApp = sink.Install(vehicles.Get(dst));
        sinkApp.Start(Seconds(0.0));
        sinkApp.Stop(Seconds(simTime));

        OnOffHelper onoff("ns3::UdpSocketFactory",
                          InetSocketAddress(interfaces.GetAddress(dst), port));
        onoff.SetConstantRate(DataRate(static_cast<uint64_t>(dataRateKbps * 1000)), packetSize);
        ApplicationContainer srcApp = onoff.Install(vehicles.Get(src));
        double start = appStart + startJitter->GetValue();
        srcApp.Start(Seconds(start));
        srcApp.Stop(Seconds(appStop));
        activeTime[port] = appStop - start;
    }

    FlowMonitorHelper flowHelper;
    Ptr<FlowMonitor> monitor = flowHelper.InstallAll();

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    monitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier =
        DynamicCast<Ipv4FlowClassifier>(flowHelper.GetClassifier());

    uint64_t txPackets = 0;
    uint64_t rxPackets = 0;
    double delaySum = 0.0;      // s
    double throughputSum = 0.0; // kbit/s, summed over flows
    for (const auto& [flowId, st] : monitor->GetFlowStats())
    {
        Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(flowId);
        // Count only the data flows, not AODV control traffic.
        if (t.protocol != 17 || activeTime.count(t.destinationPort) == 0)
        {
            continue;
        }
        txPackets += st.txPackets;
        rxPackets += st.rxPackets;
        delaySum += st.delaySum.GetSeconds();
        throughputSum +=
            st.rxPackets * packetSize * 8.0 / activeTime[t.destinationPort] / 1000.0;
    }

    double pdr = txPackets ? 100.0 * rxPackets / txPackets : 0.0;
    double lossRate =
        txPackets ? 100.0 * (static_cast<double>(txPackets) - rxPackets) / txPackets : 0.0;
    double delayMs = rxPackets ? 1000.0 * delaySum / rxPackets : std::nan("");
    double throughputKbps = throughputSum / nFlows; // mean delivered throughput per flow

    std::cout << "vehicles=" << nVehicles << " speed=" << speed << " rate=" << dataRateKbps
              << "kbps range=" << range << "m run=" << RngSeedManager::GetRun() << "\n"
              << "  tx=" << txPackets << " rx=" << rxPackets << " PDR=" << pdr
              << "% delay=" << delayMs << "ms throughput=" << throughputKbps
              << "kbps/flow loss=" << lossRate << "%" << std::endl;

    bool writeHeader = !std::ifstream(csvFile).good();
    std::ofstream out(csvFile, std::ios::app);
    if (writeHeader)
    {
        out << "experiment,nVehicles,speed,dataRateKbps,range,run,"
               "txPackets,rxPackets,pdr,delayMs,throughputKbps,lossRate\n";
    }
    out << experiment << "," << nVehicles << "," << speed << "," << dataRateKbps << "," << range
        << "," << RngSeedManager::GetRun() << "," << txPackets << "," << rxPackets << "," << pdr
        << "," << delayMs << "," << throughputKbps << "," << lossRate << "\n";

    Simulator::Destroy();
    return 0;
}
