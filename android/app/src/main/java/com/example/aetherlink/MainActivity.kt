package com.example.aetherlink

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.webkit.*
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val data: Intent? = result.data
            var results: Array<Uri>? = null
            
            if (data != null) {
                val dataString = data.dataString
                val clipData = data.clipData
                if (clipData != null) {
                    results = Array(clipData.itemCount) { i -> clipData.getItemAt(i).uri }
                } else if (dataString != null) {
                    results = arrayOf(Uri.parse(dataString))
                }
            }
            filePathCallback?.onReceiveValue(results)
        } else {
            filePathCallback?.onReceiveValue(null)
        }
        filePathCallback = null
    }

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        var allGranted = true
        permissions.forEach { (permission, isGranted) ->
            if (!isGranted) {
                allGranted = false
            }
        }
        if (!allGranted) {
            Toast.makeText(this, "Permissions required for camera, audio notes, and file sharing", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        checkAndRequestPermissions()
        
        // Enable WebView remote debugging via PC Chrome (chrome://inspect)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(true)
        }

        setContent {
            AetherLinkAppScreen()
        }
    }

    private fun checkAndRequestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.MODIFY_AUDIO_SETTINGS,
            Manifest.permission.CAMERA
        )
        
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.READ_MEDIA_IMAGES)
            permissions.add(Manifest.permission.READ_MEDIA_VIDEO)
            permissions.add(Manifest.permission.READ_MEDIA_AUDIO)
        } else {
            permissions.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

        val toRequest = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (toRequest.isNotEmpty()) {
            requestPermissionsLauncher.launch(toRequest.toTypedArray())
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun AetherLinkAppScreen() {
        val sharedPref = remember { getSharedPreferences("AetherLinkPrefs", Context.MODE_PRIVATE) }
        var serverIp by remember { mutableStateOf(sharedPref.getString("server_ip", "") ?: "") }
        var isConnected by remember { mutableStateOf(serverIp.isNotEmpty()) }

        val bgDark = Color(0xFF090F1D)
        val bgPanel = Color(0xFF0F172A)
        val neonRed = Color(0xFFEF4444)
        val textPrimary = Color(0xFFF8FAFC)
        val textMuted = Color(0xFF64748B)

        if (!isConnected) {
            var inputIp by remember { mutableStateOf("") }
            
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(bgDark),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth(0.85f)
                        .background(bgPanel, shape = RoundedCornerShape(16.dp))
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Text(
                        text = "⚡ AETHERLINK",
                        color = neonRed,
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Bold,
                        style = TextStyle(letterSpacing = 2.sp)
                    )
                    
                    Text(
                        text = "ENTER HOST SERVER IP ADDRESS",
                        color = textMuted,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        style = TextStyle(letterSpacing = 1.sp)
                    )
                    
                    OutlinedTextField(
                        value = inputIp,
                        onValueChange = { inputIp = it },
                        placeholder = { Text("e.g. 192.168.1.10", color = textMuted) },
                        textStyle = TextStyle(color = textPrimary, fontSize = 16.sp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = neonRed,
                            unfocusedBorderColor = textMuted,
                            cursorColor = neonRed,
                            focusedTextColor = textPrimary,
                            unfocusedTextColor = textPrimary
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    
                    Button(
                        onClick = {
                            if (inputIp.trim().isNotEmpty()) {
                                var formattedIp = inputIp.trim()
                                if (!formattedIp.startsWith("http://") && !formattedIp.startsWith("https://")) {
                                    // Default to local port 8080 ONLY if input is a raw IP or localhost
                                    val firstChar = formattedIp.firstOrNull()
                                    val isLocalHostOrIp = (firstChar != null && firstChar.isDigit()) || formattedIp.startsWith("localhost", ignoreCase = true)
                                    val hasPort = formattedIp.contains(":")
                                    
                                    if (isLocalHostOrIp && !hasPort) {
                                        formattedIp = "$formattedIp:8080"
                                    }
                                    
                                    // Prepend http protocol
                                    formattedIp = "http://$formattedIp"
                                }
                                sharedPref.edit().putString("server_ip", formattedIp).apply()
                                serverIp = formattedIp
                                isConnected = true
                            } else {
                                Toast.makeText(this@MainActivity, "Please enter a valid IP address", Toast.LENGTH_SHORT).show()
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = neonRed),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("CONNECT", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
            }
        } else {
            Box(modifier = Modifier.fillMaxSize()) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { context ->
                        WebView(context).apply {
                            clearCache(true)
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                                    return false
                                }

                                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                                    super.onReceivedError(view, request, error)
                                    val description = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
                                        error?.description?.toString() ?: "Connection failed"
                                    } else {
                                        "Connection failed"
                                    }
                                    Toast.makeText(view?.context, "Connection Error: $description", Toast.LENGTH_LONG).show()
                                }
                            }
                            
                            webChromeClient = object : WebChromeClient() {
                                override fun onPermissionRequest(request: PermissionRequest) {
                                    request.grant(request.resources)
                                }

                                override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
                                    val msg = consoleMessage?.message() ?: ""
                                    val source = consoleMessage?.sourceId() ?: ""
                                    val line = consoleMessage?.lineNumber() ?: 0
                                    val level = consoleMessage?.messageLevel()
                                    
                                    android.util.Log.d("WebViewConsole", "[$level] $msg ($source:$line)")
                                    
                                    if (level == ConsoleMessage.MessageLevel.ERROR) {
                                        Toast.makeText(this@MainActivity, "JS Error: $msg\nAt: $source:$line", Toast.LENGTH_LONG).show()
                                    }
                                    return true
                                }

                                override fun onShowFileChooser(
                                    webView: WebView?,
                                    filePathCallback: ValueCallback<Array<Uri>>?,
                                    fileChooserParams: FileChooserParams?
                                ): Boolean {
                                    this@MainActivity.filePathCallback?.onReceiveValue(null)
                                    this@MainActivity.filePathCallback = filePathCallback

                                    val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                                        type = "*/*"
                                        addCategory(Intent.CATEGORY_OPENABLE)
                                    }
                                    
                                    try {
                                        fileChooserLauncher.launch(intent)
                                    } catch (e: Exception) {
                                        this@MainActivity.filePathCallback?.onReceiveValue(null)
                                        this@MainActivity.filePathCallback = null
                                        Toast.makeText(this@MainActivity, "Cannot open file picker", Toast.LENGTH_SHORT).show()
                                        return false
                                    }
                                    return true
                                }
                            }
                            
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.allowFileAccess = true
                            settings.allowContentAccess = true
                            settings.mediaPlaybackRequiresUserGesture = false
                            
                            loadUrl(serverIp)
                        }
                    }
                )
                
                FloatingActionButton(
                    onClick = {
                        sharedPref.edit().remove("server_ip").apply()
                        serverIp = ""
                        isConnected = false
                    },
                    containerColor = neonRed,
                    contentColor = Color.White,
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(16.dp)
                        .size(44.dp)
                ) {
                    Text(
                        text = "⚙️",
                        fontSize = 20.sp
                    )
                }
            }
        }
    }
}
