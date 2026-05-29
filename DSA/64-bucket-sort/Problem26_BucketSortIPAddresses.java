import java.util.*;
public class Problem26_BucketSortIPAddresses {
    public String[] sortIPs(String[] ips) {
        Arrays.sort(ips, (a,b) -> { String[] pa=a.split("\\."),pb=b.split("\\.");
            for(int i=0;i<4;i++){int diff=Integer.parseInt(pa[i])-Integer.parseInt(pb[i]);if(diff!=0) return diff;} return 0; });
        return ips;
    }
    public static void main(String[] args){ String[] ips={"192.168.1.1","10.0.0.1","172.16.0.1","192.168.0.1"}; new Problem26_BucketSortIPAddresses().sortIPs(ips); System.out.println(Arrays.toString(ips)); }
}
