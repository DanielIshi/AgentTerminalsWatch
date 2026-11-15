import com.spockymagicai.agentterminals.NotificationPolicy;
public class NotificationPolicyTest {
 static void require(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  require(NotificationPolicy.shouldNotify("needs_input",4,3));
  require(NotificationPolicy.shouldNotify("completed",4,3));
  require(NotificationPolicy.shouldNotify("failed",4,3));
  require(!NotificationPolicy.shouldNotify("in_progress",4,3));
  require(!NotificationPolicy.shouldNotify("completed",4,4));
  require(!NotificationPolicy.shouldNotify("completed",3,4));
  System.out.println("Notification status/version dedup tests passed");
 }
}
