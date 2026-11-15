package com.spockymagicai.agentterminals;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/* loaded from: classes2.dex */
public final class TerminalActivity extends Activity {
    private static final int CONTROL_HEIGHT_DP = 24;
    private static final String EXTRA_NAME = "session-name";
    private static final String EXTRA_SESSION_ID = "session-id";
    private static final String PREFS = "agent-terminals";
    private static final String PREF_ADVANCED_CONTROLS = "advanced-controls";
    private boolean advancedControls;
    private LinearLayout controls;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private EditText inputText;
    private LinearLayout root;
    private String sessionId;
    private TextView statusText;
    private boolean stopped;
    private ScrollView terminalScroll;
    private TextView terminalText;

    public static void open(Context context, String sessionId, String name) {
        Intent intent = new Intent(context, (Class<?>) TerminalActivity.class);
        intent.putExtra(EXTRA_SESSION_ID, sessionId);
        intent.putExtra(EXTRA_NAME, name);
        context.startActivity(intent);
    }

    @Override // android.app.Activity
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(128);
        String name = getIntent().getStringExtra(EXTRA_NAME);
        this.sessionId = getIntent().getStringExtra(EXTRA_SESSION_ID);
        setTitle(name);
        this.advancedControls = getSharedPreferences(PREFS, 0).getBoolean(PREF_ADVANCED_CONTROLS, false);
        this.root = new LinearLayout(this);
        this.root.setOrientation(1);
        this.root.setPadding(4, 3, 4, dp(18));
        this.root.setBackgroundColor(Color.rgb(8, 8, 8));
        LinearLayout header = new LinearLayout(this);
        header.setOrientation(0);
        header.setGravity(16);
        this.statusText = new TextView(this);
        this.statusText.setText(name + " connecting...");
        this.statusText.setTextColor(Color.rgb(180, 220, 180));
        this.statusText.setTextSize(8.0f);
        this.statusText.setGravity(17);
        this.statusText.setSingleLine(true);
        header.addView(this.statusText, new LinearLayout.LayoutParams(0, -2, 1.0f));
        TextView tools = compactHeaderControl("Tools");
        tools.setContentDescription("Toggle extra terminal controls");
        tools.setOnClickListener(new View.OnClickListener() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda1
            @Override // android.view.View.OnClickListener
            public final void onClick(View view) {
                TerminalActivity.this.m0xf6416683(view);
            }
        });
        header.addView(tools, new LinearLayout.LayoutParams(dp(45), dp(18)));
        this.root.addView(header);
        this.terminalText = new TextView(this);
        this.terminalText.setTextColor(Color.rgb(230, 230, 230));
        this.terminalText.setTextSize(6.0f);
        this.terminalText.setTypeface(Typeface.MONOSPACE);
        this.terminalText.setTextIsSelectable(false);
        this.terminalText.setIncludeFontPadding(false);
        this.terminalText.setLineSpacing(0.0f, 0.86f);
        this.terminalText.setPadding(0, 2, 0, 2);
        this.terminalScroll = new ScrollView(this);
        this.terminalScroll.addView(this.terminalText);
        this.root.addView(this.terminalScroll, new LinearLayout.LayoutParams(-1, 0, 1.0f));
        this.controls = new LinearLayout(this);
        this.controls.setOrientation(0);
        this.controls.setPadding(dp(20), 0, dp(28), 0);
        renderControls();
        this.root.addView(this.controls);
        setContentView(this.root);
        refreshTerminal();
        scheduleRefresh();
    }

    /* renamed from: lambda$onCreate$0$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m0xf6416683(View v) {
        toggleAdvancedControls();
    }

    @Override // android.app.Activity
    protected void onDestroy() {
        this.stopped = true;
        this.handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void scheduleRefresh() {
        this.handler.postDelayed(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda4
            @Override // java.lang.Runnable
            public final void run() {
                TerminalActivity.this.m8xdeb7d433();
            }
        }, 5000L);
    }

    /* renamed from: lambda$scheduleRefresh$1$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m8xdeb7d433() {
        if (!this.stopped) {
            refreshTerminal();
            scheduleRefresh();
        }
    }

    private void refreshTerminal() {
        setStatus("Refreshing...");
        new Thread(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda10
            @Override // java.lang.Runnable
            public final void run() {
                TerminalActivity.this.m3x20ff3829();
            }
        }).start();
    }

    /* renamed from: lambda$refreshTerminal$4$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m3x20ff3829() {
        try {
            final String text = new SecureGatewayClient(this).captureTerminal(this.sessionId);
            runOnUiThread(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda7
                @Override // java.lang.Runnable
                public final void run() {
                    TerminalActivity.this.m1x99e8fca7(text);
                }
            });
        } catch (Exception e) {
            Log.e("AgentTerminals", "TERMINAL_REFRESH_ERROR", e);
            runOnUiThread(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda8
                @Override // java.lang.Runnable
                public final void run() {
                    TerminalActivity.this.m2xdd741a68(e);
                }
            });
        }
    }

    /* renamed from: lambda$refreshTerminal$2$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m1x99e8fca7(String text) {
        int previousScrollY = this.terminalScroll.getScrollY();
        boolean stayAtBottom = isScrolledToBottom();
        this.terminalText.setText(text);
        restoreScrollPosition(previousScrollY, stayAtBottom);
        setStatus("Live");
    }

    /* renamed from: lambda$refreshTerminal$3$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m2xdd741a68(Exception e) {
        setStatus("Refresh error: " + e.getMessage());
    }

    private void renderControls() {
        this.controls.removeAllViews();
        this.inputText = new EditText(this);
        this.inputText.setSingleLine(true);
        this.inputText.setTextColor(-1);
        this.inputText.setHintTextColor(-7829368);
        this.inputText.setHint("Speak or type");
        this.inputText.setTextSize(8.0f);
        this.inputText.setMinHeight(0);
        this.inputText.setMinimumHeight(0);
        this.inputText.setIncludeFontPadding(false);
        this.inputText.setPadding(3, 0, 3, 0);
        this.inputText.setBackground(compactBackground(Color.rgb(26, 26, 26), Color.rgb(80, 80, 80)));
        this.controls.addView(this.inputText, new LinearLayout.LayoutParams(0, dp(CONTROL_HEIGHT_DP), this.advancedControls ? 3.1f : 3.8f));
        if (this.advancedControls) {
            TextView refresh = compactControl("Ref");
            refresh.setContentDescription("Refresh terminal");
            refresh.setOnClickListener(new View.OnClickListener() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda0
                @Override // android.view.View.OnClickListener
                public final void onClick(View view) {
                    TerminalActivity.this.m4xc036b1b9(view);
                }
            });
            this.controls.addView(refresh, new LinearLayout.LayoutParams(0, dp(CONTROL_HEIGHT_DP), 0.7f));
            TextView send = compactControl("Send");
            send.setContentDescription("Send text without enter");
            send.setOnClickListener(new View.OnClickListener() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda2
                @Override // android.view.View.OnClickListener
                public final void onClick(View view) {
                    TerminalActivity.this.m5x3c1cf7a(view);
                }
            });
            this.controls.addView(send, new LinearLayout.LayoutParams(0, dp(CONTROL_HEIGHT_DP), 0.95f));
        }
        TextView enter = compactControl("OK");
        enter.setContentDescription("Send text and press enter");
        enter.setOnClickListener(new View.OnClickListener() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda3
            @Override // android.view.View.OnClickListener
            public final void onClick(View view) {
                TerminalActivity.this.m6x474ced3b(view);
            }
        });
        this.controls.addView(enter, new LinearLayout.LayoutParams(0, dp(CONTROL_HEIGHT_DP), 0.7f));
    }

    /* renamed from: lambda$renderControls$5$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m4xc036b1b9(View v) {
        refreshTerminal();
    }

    /* renamed from: lambda$renderControls$6$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m5x3c1cf7a(View v) {
        sendInput(false);
    }

    /* renamed from: lambda$renderControls$7$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m6x474ced3b(View v) {
        sendInput(true);
    }

    private void toggleAdvancedControls() {
        this.advancedControls = !this.advancedControls;
        getSharedPreferences(PREFS, 0).edit().putBoolean(PREF_ADVANCED_CONTROLS, this.advancedControls).apply();
        renderControls();
        setStatus(this.advancedControls ? "Extra controls on" : "Extra controls off");
    }

    private void sendInput(final boolean pressEnter) {
        final String text = this.inputText.getText().toString();
        this.inputText.setText("");
        setStatus("Sending...");
        new Thread(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda5
            @Override // java.lang.Runnable
            public final void run() {
                TerminalActivity.this.m10xa0d5a259(text, pressEnter);
            }
        }).start();
    }

    /* renamed from: lambda$sendInput$9$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m10xa0d5a259(String text, boolean pressEnter) {
        try {
            SecureGatewayClient client = new SecureGatewayClient(this);
            client.sendTerminalInput(this.sessionId, text, pressEnter);
            if (pressEnter) {
                Thread.sleep(1000L);
                client.sendTerminalInput(this.sessionId, "", true);
            }
            refreshTerminal();
        } catch (Exception e) {
            Log.e("AgentTerminals", "TERMINAL_SEND_ERROR", e);
            runOnUiThread(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda9
                @Override // java.lang.Runnable
                public final void run() {
                    TerminalActivity.this.m9x5d4a8498(e);
                }
            });
        }
    }

    /* renamed from: lambda$sendInput$8$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m9x5d4a8498(Exception e) {
        setStatus("Send error: " + e.getMessage());
    }

    private void setStatus(String text) {
        this.statusText.setText(text);
    }

    private boolean isScrolledToBottom() {
        if (this.terminalScroll == null || this.terminalScroll.getChildCount() == 0) {
            return true;
        }
        int maxScroll = Math.max(0, this.terminalScroll.getChildAt(0).getHeight() - this.terminalScroll.getHeight());
        return this.terminalScroll.getScrollY() >= maxScroll - dp(8);
    }

    private void restoreScrollPosition(final int previousScrollY, final boolean stayAtBottom) {
        this.terminalScroll.post(new Runnable() { // from class: com.spockymagicai.agentterminals.TerminalActivity$$ExternalSyntheticLambda6
            @Override // java.lang.Runnable
            public final void run() {
                TerminalActivity.this.m7xa039b1bb(stayAtBottom, previousScrollY);
            }
        });
    }

    /* renamed from: lambda$restoreScrollPosition$10$com-spockymagicai-agentterminals-TerminalActivity, reason: not valid java name */
    /* synthetic */ void m7xa039b1bb(boolean stayAtBottom, int previousScrollY) {
        if (stayAtBottom) {
            this.terminalScroll.fullScroll(130);
        } else {
            int maxScroll = Math.max(0, this.terminalScroll.getChildAt(0).getHeight() - this.terminalScroll.getHeight());
            this.terminalScroll.scrollTo(0, Math.min(previousScrollY, maxScroll));
        }
    }

    private TextView compactControl(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(-1);
        view.setTextSize(7.0f);
        view.setGravity(17);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setIncludeFontPadding(false);
        view.setBackground(compactBackground(Color.rgb(34, 34, 34), Color.rgb(86, 86, 86)));
        view.setClickable(true);
        view.setFocusable(true);
        return view;
    }

    private TextView compactHeaderControl(String text) {
        TextView view = compactControl(text);
        view.setTextSize(7.0f);
        return view;
    }

    private GradientDrawable compactBackground(int fill, int stroke) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setStroke(1, stroke);
        drawable.setCornerRadius(dp(5));
        return drawable;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
