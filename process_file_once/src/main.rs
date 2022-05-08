extern crate redis;
use std::env;
use std::fs;
use std::process::Command;

const KEY_NAME: &str = "process_once";

fn main() -> Result<(), redis::RedisError> {
    let args: Vec<String> = env::args().collect();
    let filename = fs::canonicalize(&args[1])
        .unwrap()
        .into_os_string()
        .into_string()
        .unwrap();
    let params: Vec<String> = args[2..]
        .iter()
        .map(|s| s.replace("{}", &filename.to_string()))
        .collect();
    let args_string = args[2..].join("\0");
    let key = format!("{}\0{}", filename, args_string);

    let client = redis::Client::open("redis+unix:///var/run/redis/redis-server.sock")?;
    let mut con = client.get_connection()?;
    let count: i64 = redis::cmd("SISMEMBER")
        .arg(KEY_NAME)
        .arg(&key)
        .query(&mut con)?;
    if count == 0 {
        let output = Command::new(String::from(&params[0]))
            .args(params[1..].iter())
            .output()
            .expect("invoke worked");
        assert!(output.status.success());
        redis::cmd("SADD").arg(KEY_NAME).arg(&key).query(&mut con)?;
    }

    Ok(())
}
