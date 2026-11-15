package com.spockymagicai.agentterminals;
import java.util.Locale;
public final class RequestPolicy {
    private RequestPolicy(){}
    public static String kind(String text){
        String value=text.trim().toLowerCase(Locale.GERMAN).replaceFirst("^ceo[, :]*","");
        return value.matches("(?s)^(was läuft|was braucht meine entscheidung|wie weit ist|wie ist der status|status von|welche aufträge|was ist fertig).*?")?"query":"task";
    }
}
