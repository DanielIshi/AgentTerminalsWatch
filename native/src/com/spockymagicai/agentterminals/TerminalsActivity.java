package com.spockymagicai.agentterminals;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

/* loaded from: classes2.dex */
public class TerminalsActivity extends Activity implements View.OnClickListener {
    private static final String[][] SESSIONS = {new String[]{"ceo", "CEO"}, new String[]{"marketing", "MKT"}, new String[]{"strategy", "STR"}, new String[]{"operations", "OPS"}, new String[]{"ict", "ICT"}};
    private TextView statusText;

    @Override // android.app.Activity
    protected void onCreate(Bundle savedInstanceState) {
        TextView tile;
        super.onCreate(savedInstanceState);
        getWindow().addFlags(128);
        LinearLayout linearLayout = new LinearLayout(this);
        linearLayout.setOrientation(1);
        linearLayout.setGravity(1);
        linearLayout.setPadding(14, 10, 14, 10);
        linearLayout.setBackgroundColor(Color.rgb(17, 17, 17));
        TextView title = new TextView(this);
        title.setText("Agent Terminals");
        title.setTextColor(-1);
        title.setTextSize(14.0f);
        title.setGravity(17);
        linearLayout.addView(title);
        this.statusText = new TextView(this);
        this.statusText.setTextColor(Color.rgb(238, 238, 238));
        this.statusText.setTextSize(9.0f);
        this.statusText.setGravity(17);
        this.statusText.setPadding(0, 3, 0, 5);
        linearLayout.addView(this.statusText);
        LinearLayout linearLayout2 = new LinearLayout(this);
        linearLayout2.setOrientation(1);
        for (int row = 0; row < 3; row++) {
            LinearLayout line = new LinearLayout(this);
            line.setOrientation(0);
            line.setGravity(17);
            linearLayout2.addView(line, new LinearLayout.LayoutParams(-1, dp(56)));
            for (int column = 0; column < 2; column++) {
                int index = (row * 2) + column;
                if (index < SESSIONS.length) {
                    tile = gridButton(SESSIONS[index][1]);
                    tile.setTag(SESSIONS[index]);
                } else {
                    TextView tile2 = gridButton("Exit");
                    tile2.setTag(new String[]{"exit", "Exit"});
                    tile = tile2;
                }
                tile.setOnClickListener(this);
                line.addView(tile, tileParams());
            }
        }
        linearLayout.addView(linearLayout2);
        setContentView(linearLayout);
        initializeIdentity();
    }

    @Override // android.view.View.OnClickListener
    public void onClick(View view) {
        String[] session = (String[]) view.getTag();
        if ("exit".equals(session[0])) {
            finishAndRemoveTask();
        } else {
            new Thread(new OpenTerminalTask(this, session[0], session[1])).start();
        }
    }

    private void initializeIdentity() {
        setStatus("Initializing device identity...");
        new Thread(new IdentityTask(this)).start();
    }

    private void connect() {
        setStatus("Connecting with client certificate...");
        new Thread(new ConnectTask(this)).start();
    }

    public void connectAfterIdentityReady() {
        connect();
    }

    public void setStatus(String text) {
        runOnUiThread(new SetStatusTask(this.statusText, text));
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView gridButton(String text) {
        TextView button = new TextView(this);
        button.setText(text);
        button.setTextColor(-1);
        button.setTextSize(16.0f);
        button.setTypeface(Typeface.DEFAULT_BOLD);
        button.setGravity(17);
        button.setIncludeFontPadding(false);
        button.setBackground(tileBackground("Exit".equals(text)));
        button.setClickable(true);
        button.setFocusable(true);
        return button;
    }

    private LinearLayout.LayoutParams tileParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, dp(50), 1.0f);
        params.setMargins(dp(3), dp(3), dp(3), dp(3));
        return params;
    }

    private GradientDrawable tileBackground(boolean exit) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(exit ? Color.rgb(45, 24, 24) : Color.rgb(28, 31, 34));
        drawable.setStroke(1, exit ? Color.rgb(120, 70, 70) : Color.rgb(78, 84, 90));
        drawable.setCornerRadius(dp(8));
        return drawable;
    }
}
