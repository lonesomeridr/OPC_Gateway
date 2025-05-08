# OPC UA to Unity Connector

This package provides a simple way to connect OPC UA data to Unity using a HTTP API server.

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- OPC UA server with the tags you want to monitor
- Unity (on the client side)

### Installation

1. Install required Python packages:

```bash
pip install -r requirements.txt
```

2. Configure the connection:

Edit `config.ini` to set:
- OPC UA server details in the `[OPCUA]` section
- HTTP server settings in the `[HTTP]` section
- Tags to monitor in the `[MONITORING]` section

3. Run the connector:

```bash
python unity_connector.py
```

4. Test the connection:

Open a web browser and navigate to:
```
http://localhost:5000/api/values
```

You should see JSON data with your OPC UA values.

### Unity Integration

In Unity, create a new script called `OpcUaHttpClient.cs` with this code:

```csharp
using UnityEngine;
using System;
using System.Collections;
using UnityEngine.Networking;
using TMPro;
using System.Collections.Generic;

[Serializable]
public class OpcValueData
{
    public float value;
    public string unit;
    public string timestamp;
}

[Serializable]
public class OpcValuesResponse
{
    public Dictionary<string, OpcValueData> values;
}

public class OpcUaHttpClient : MonoBehaviour
{
    [Header("API Configuration")]
    public string apiUrl = "http://localhost:5000";
    public float updateInterval = 0.1f;
    
    [Header("UI Elements")]
    public TextMeshProUGUI flowValueText;
    
    // Latest values
    private float currentFlowValue;
    private Dictionary<string, OpcValueData> latestValues = new Dictionary<string, OpcValueData>();
    
    void Start()
    {
        StartCoroutine(UpdateValuesRoutine());
    }
    
    void Update()
    {
        // Update UI if we have values
        if (flowValueText != null && latestValues.ContainsKey("FlowTransmitter"))
        {
            var flowData = latestValues["FlowTransmitter"];
            flowValueText.text = $"Flow: {flowData.value:F2} {flowData.unit}";
        }
    }
    
    IEnumerator UpdateValuesRoutine()
    {
        while (true)
        {
            // Request values
            yield return StartCoroutine(FetchValues());
            
            // Wait for next update interval
            yield return new WaitForSeconds(updateInterval);
        }
    }
    
    IEnumerator FetchValues()
    {
        string url = $"{apiUrl}/api/values";
        
        using (UnityWebRequest request = UnityWebRequest.Get(url))
        {
            // Send request
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    // Parse response
                    string json = request.downloadHandler.text;
                    
                    // Unity's built-in JSON parsing doesn't handle dictionaries well, 
                    // so we parse manually for this simple case
                    ParseJson(json);
                }
                catch (Exception ex)
                {
                    Debug.LogError($"Error parsing API response: {ex.Message}");
                }
            }
            else
            {
                Debug.LogError($"Error fetching values: {request.error}");
            }
        }
    }
    
    private void ParseJson(string json)
    {
        // Simple manual parsing - for production, use a proper JSON library like Newtonsoft.Json
        try 
        {
            // Find FlowTransmitter section
            int flowStart = json.IndexOf("\"FlowTransmitter\"");
            if (flowStart >= 0)
            {
                // Extract value
                int valueStart = json.IndexOf("\"value\":", flowStart);
                if (valueStart >= 0)
                {
                    valueStart += 8; // Length of "\"value\":"
                    int valueEnd = json.IndexOf(",", valueStart);
                    if (valueEnd < 0) valueEnd = json.IndexOf("}", valueStart);
                    
                    string valueStr = json.Substring(valueStart, valueEnd - valueStart);
                    float value = float.Parse(valueStr);
                    
                    // Extract unit
                    int unitStart = json.IndexOf("\"unit\":\"", flowStart);
                    unitStart += 8; // Length of "\"unit\":\""
                    int unitEnd = json.IndexOf("\"", unitStart);
                    string unit = json.Substring(unitStart, unitEnd - unitStart);
                    
                    // Create data object
                    if (!latestValues.ContainsKey("FlowTransmitter"))
                    {
                        latestValues["FlowTransmitter"] = new OpcValueData();
                    }
                    
                    latestValues["FlowTransmitter"].value = value;
                    latestValues["FlowTransmitter"].unit = unit;
                    
                    Debug.Log($"Updated flow value: {value} {unit}");
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error parsing JSON: {ex.Message}");
        }
    }
}
```

Attach this script to a GameObject in your Unity scene and configure the API URL to point to your Python server.

### Network Configuration

If running on different computers:

1. Make sure the Python script is running on a machine that can reach the OPC UA server
2. Use the server's IP address in Unity rather than 'localhost'
3. Ensure the port (default: 5000) is open in any firewalls

### Troubleshooting

- If Unity can't connect, check network connectivity and firewall settings
- If no values appear, verify the OPC UA connection is working
- Check the Python console for error messages