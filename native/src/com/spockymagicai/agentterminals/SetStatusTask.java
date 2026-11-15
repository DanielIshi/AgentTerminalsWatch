package com.spockymagicai.agentterminals;

import android.widget.TextView;

/* loaded from: classes2.dex */
public final class SetStatusTask implements Runnable {
    private final String text;
    private final TextView textView;

    public SetStatusTask(TextView textView, String text) {
        this.textView = textView;
        this.text = text;
    }

    @Override // java.lang.Runnable
    public void run() {
        this.textView.setText(this.text);
    }
}
