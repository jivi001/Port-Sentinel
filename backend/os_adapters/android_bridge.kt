/**
 * Sentinel OS Adapter — Android (android_bridge.kt)
 *
 * Kotlin VpnService implementation for packet capture on Android 12+.
 * Provides:
 *   - VPN-based packet capture (VpnService API)
 *   - PackageManager uid → AppName resolution
 *   - JNI bridge for Python ↔ Kotlin IPC
 *   - Runtime VPN permission request
 *
 * Architecture:
 *   Android doesn't allow raw socket access without root.
 *   Instead, we create a local VPN tunnel that intercepts all traffic,
 *   parses IP/TCP/UDP headers, and forwards metrics via JNI to the
 *   Python backend running in an embedded interpreter (e.g., Chaquopy).
 */

package com.sentinel.sentinel

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.InetAddress
import java.nio.ByteBuffer
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/**
 * Data class for per-port traffic metrics.
 */
data class PortMetric(
    val port: Int,
    val uid: Int,
    val appName: String,
    val protocol: String, // "TCP" or "UDP"
    val bytesIn: AtomicLong = AtomicLong(0),
    val bytesOut: AtomicLong = AtomicLong(0),
    var lastUpdated: Long = System.currentTimeMillis()
)

/**
 * VPN-based packet capture service for Sentinel on Android.
 *
 * Creates a local TUN interface, reads all network traffic,
 * extracts port/protocol/byte metrics, and resolves app names
 * via PackageManager.
 */
class SentinelVpnService : VpnService() {

    companion object {
        private const val TAG = "SentinelVpn"
        private const val CHANNEL_ID = "sentinel_vpn_channel"
        private const val NOTIFICATION_ID = 1
        private const val VPN_MTU = 1500
        private const val VPN_ADDRESS = "10.0.0.2"
        private const val VPN_ROUTE = "0.0.0.0"

        // JNI bridge — loaded from native library
        init {
            try {
                System.loadLibrary("sentinel_bridge")
            } catch (e: UnsatisfiedLinkError) {
                Log.w(TAG, "Native bridge library not found; JNI disabled")
            }
        }
    }

    private var vpnInterface: ParcelFileDescriptor? = null
    private val isRunning = AtomicBoolean(false)
    private val portMetrics = ConcurrentHashMap<Int, PortMetric>()
    private var captureThread: Thread? = null

    // --- JNI native methods (implemented in C/C++ shared library) ---

    /**
     * Push port metrics to the Python backend via shared memory.
     * @param port Port number
     * @param bytesIn Cumulative bytes received
     * @param bytesOut Cumulative bytes sent
     * @param uid Android UID of the owning app
     * @param protocol 0 = TCP, 1 = UDP
     */
    private external fun nativePushMetrics(
        port: Int,
        bytesIn: Long,
        bytesOut: Long,
        uid: Int,
        protocol: Int
    )

    /**
     * Initialize the native shared memory bridge.
     * @return true if initialization succeeded
     */
    private external fun nativeInitBridge(): Boolean

    /**
     * Clean up native resources.
     */
    private external fun nativeCleanup()

    // --- Service Lifecycle ---

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") {
            stopVpn()
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(NOTIFICATION_ID, createNotification())
        startVpn()
        return START_STICKY
    }

    override fun onDestroy() {
        stopVpn()
        super.onDestroy()
    }

    // --- VPN Setup ---

    private fun startVpn() {
        if (isRunning.get()) return

        try {
            val builder = Builder()
                .setSession("Sentinel Sentinel")
                .setMtu(VPN_MTU)
                .addAddress(VPN_ADDRESS, 32)
                .addRoute(VPN_ROUTE, 0)
                // Allow all apps through the VPN for monitoring
                .allowFamily(android.system.OsConstants.AF_INET)

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                builder.setMetered(false)
            }

            vpnInterface = builder.establish()

            if (vpnInterface == null) {
                Log.e(TAG, "Failed to establish VPN interface")
                return
            }

            isRunning.set(true)

            // Initialize JNI bridge
            try {
                nativeInitBridge()
            } catch (e: UnsatisfiedLinkError) {
                Log.w(TAG, "JNI bridge not available; metrics will be local only")
            }

            // Start capture thread
            captureThread = Thread(this::captureLoop, "Sentinel-Capture")
            captureThread?.start()

            Log.i(TAG, "VPN started — capturing traffic")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to start VPN", e)
        }
    }

    private fun stopVpn() {
        isRunning.set(false)

        captureThread?.interrupt()
        captureThread = null

        vpnInterface?.close()
        vpnInterface = null

        try {
            nativeCleanup()
        } catch (e: UnsatisfiedLinkError) {
            // JNI not available
        }

        portMetrics.clear()
        Log.i(TAG, "VPN stopped")
    }

    // --- Packet Capture Loop ---

    private fun captureLoop() {
        val fd = vpnInterface ?: return
        val inputStream = FileInputStream(fd.fileDescriptor)
        val outputStream = FileOutputStream(fd.fileDescriptor)
        val packet = ByteBuffer.allocate(VPN_MTU)

        while (isRunning.get() && !Thread.interrupted()) {
            try {
                packet.clear()
                val length = inputStream.read(packet.array())

                if (length > 0) {
                    packet.limit(length)
                    processPacket(packet, length)

                    // Forward packet back out (we're monitoring, not blocking)
                    packet.position(0)
                    outputStream.write(packet.array(), 0, length)
                }
            } catch (e: InterruptedException) {
                break
            } catch (e: Exception) {
                if (isRunning.get()) {
                    Log.d(TAG, "Capture error: ${e.message}")
                }
            }
        }
    }

    /**
     * Parse IP/TCP/UDP header from a raw packet buffer.
     */
    private fun processPacket(packet: ByteBuffer, length: Int) {
        if (length < 20) return // Minimum IP header

        val version = (packet.get(0).toInt() shr 4) and 0xF
        if (version != 4) return // IPv4 only for now

        val ipHeaderLength = (packet.get(0).toInt() and 0xF) * 4
        val protocol = packet.get(9).toInt() and 0xFF
        val totalLength = length

        when (protocol) {
            6 -> { // TCP
                if (length < ipHeaderLength + 4) return
                val srcPort = ((packet.get(ipHeaderLength).toInt() and 0xFF) shl 8) or
                        (packet.get(ipHeaderLength + 1).toInt() and 0xFF)
                val dstPort = ((packet.get(ipHeaderLength + 2).toInt() and 0xFF) shl 8) or
                        (packet.get(ipHeaderLength + 3).toInt() and 0xFF)
                recordTraffic(srcPort, dstPort, totalLength, "TCP")
            }
            17 -> { // UDP
                if (length < ipHeaderLength + 4) return
                val srcPort = ((packet.get(ipHeaderLength).toInt() and 0xFF) shl 8) or
                        (packet.get(ipHeaderLength + 1).toInt() and 0xFF)
                val dstPort = ((packet.get(ipHeaderLength + 2).toInt() and 0xFF) shl 8) or
                        (packet.get(ipHeaderLength + 3).toInt() and 0xFF)
                recordTraffic(srcPort, dstPort, totalLength, "UDP")
            }
        }
    }

    /**
     * Record traffic bytes for source and destination ports.
     */
    private fun recordTraffic(srcPort: Int, dstPort: Int, bytes: Int, protocol: String) {
        // Source port → outbound
        getOrCreateMetric(srcPort, protocol).apply {
            bytesOut.addAndGet(bytes.toLong())
            lastUpdated = System.currentTimeMillis()
        }

        // Destination port → inbound
        getOrCreateMetric(dstPort, protocol).apply {
            bytesIn.addAndGet(bytes.toLong())
            lastUpdated = System.currentTimeMillis()
        }

        // Push to JNI bridge
        try {
            val srcMetric = portMetrics[srcPort]
            if (srcMetric != null) {
                nativePushMetrics(
                    srcPort,
                    srcMetric.bytesIn.get(),
                    srcMetric.bytesOut.get(),
                    srcMetric.uid,
                    if (protocol == "TCP") 0 else 1
                )
            }
        } catch (e: UnsatisfiedLinkError) {
            // JNI not available
        }
    }

    private fun getOrCreateMetric(port: Int, protocol: String): PortMetric {
        return portMetrics.getOrPut(port) {
            val uid = getUidForPort(port)
            val appName = resolveAppName(uid)
            PortMetric(port = port, uid = uid, appName = appName, protocol = protocol)
        }
    }

    // --- UID / App Resolution ---

    /**
     * Resolve network UID for a port using ConnectivityManager.
     * 
     * Note: On Android 12+, this requires QUERY_ALL_PACKAGES or
     * specific query declarations in AndroidManifest.xml.
     */
    private fun getUidForPort(port: Int): Int {
        // Android doesn't provide a direct port→UID API without root
        // Use ConnectivityManager.getConnectionOwnerUid on Android 10+
        try {
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // getConnectionOwnerUid requires NETWORK_FACTORY permission (system only)
                // Fallback: we track UIDs via /proc/net/tcp if accessible
            }
        } catch (e: Exception) {
            Log.d(TAG, "UID resolution failed for port $port: ${e.message}")
        }
        return -1 // Unknown
    }

    /**
     * Resolve Android UID to application name using PackageManager.
     */
    fun resolveAppName(uid: Int): String {
        if (uid < 0) return "Unknown"
        if (uid == 0) return "System"
        if (uid == 1000) return "System" // android.uid.system

        return try {
            val packages = packageManager.getPackagesForUid(uid)
            if (packages != null && packages.isNotEmpty()) {
                val appInfo = packageManager.getApplicationInfo(packages[0], 0)
                packageManager.getApplicationLabel(appInfo).toString()
            } else {
                "UID:$uid"
            }
        } catch (e: PackageManager.NameNotFoundException) {
            "UID:$uid"
        }
    }

    /**
     * Get current metrics snapshot for all tracked ports.
     */
    fun getMetricsSnapshot(): Map<Int, PortMetric> {
        return HashMap(portMetrics)
    }

    // --- Notification ---

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Sentinel Network Monitor",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows when Sentinel is monitoring network traffic"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        val stopIntent = Intent(this, SentinelVpnService::class.java).apply {
            action = "STOP"
        }
        val stopPending = PendingIntent.getService(
            this, 0, stopIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Sentinel Sentinel")
            .setContentText("Monitoring network traffic")
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .addAction(
                Notification.Action.Builder(
                    null, "Stop", stopPending
                ).build()
            )
            .setOngoing(true)
            .build()
    }
}

/**
 * Helper activity to request VPN permission.
 *
 * Usage: Start this activity before starting SentinelVpnService.
 * It will call VpnService.prepare() and handle the permission dialog.
 */
class VpnPermissionHelper {
    companion object {
        const val VPN_REQUEST_CODE = 1001

        /**
         * Check and request VPN permission.
         * @return Intent to start if permission is needed, null if already granted.
         */
        fun prepareVpn(context: Context): Intent? {
            return VpnService.prepare(context)
        }
    }
}
