import java.util.*;
public class Problem47_BucketSortLoadDistribution {
    /* Distribute items to servers by bucket assignment */
    public List<List<Integer>> distribute(int[] items, int numServers) {
        int min=Integer.MAX_VALUE,max=Integer.MIN_VALUE; for(int x:items){min=Math.min(min,x);max=Math.max(max,x);}
        int range=Math.max(1,(max-min+numServers)/numServers);
        List<List<Integer>> servers=new ArrayList<>(); for(int i=0;i<numServers;i++) servers.add(new ArrayList<>());
        for(int x:items) servers.get(Math.min((x-min)/range,numServers-1)).add(x);
        return servers;
    }
    public static void main(String[] args){ System.out.println(new Problem47_BucketSortLoadDistribution().distribute(new int[]{1,15,3,22,8,12,19,5,25,10},3)); }
}
